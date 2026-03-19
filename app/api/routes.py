"""FastAPI route handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    HealthResponse,
    MetaResponse,
    RouteRequest,
    RouteResponse,
    RouteStop,
    ScoreRequest,
    ScoreResponse,
)
from app.core.config import settings
from app.data.data_loader import load_csv, _hash_id
from app.data.synthetic_geo import assign_coordinates
from app.db.session import get_db
from app.ml.predictor import get_predictor
from app.optimization.distance_provider import get_provider
from app.optimization.ortools_tsp import solve_tsp

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


@router.get("/meta", response_model=MetaResponse)
def meta():
    return MetaResponse(
        service="salespilot",
        version="0.1.0",
        model_version=settings.MODEL_VERSION,
    )


@router.post("/v1/load-data")
def load_data(csv_dir: str = "data/raw"):
    """Trigger the CSV → PostgreSQL data pipeline."""
    try:
        counts = load_csv(csv_dir)
        return {"status": "ok", "rows_loaded": counts}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/v1/score-accounts", response_model=ScoreResponse)
def score_accounts(request: ScoreRequest, db: Session = Depends(get_db)):
    predictor = get_predictor()
    scores = predictor.score_accounts(request.account_ids, db)
    return ScoreResponse(scores=scores, model_version=settings.MODEL_VERSION)


@router.post("/v1/optimize-route", response_model=RouteResponse)
def optimize_route(request: RouteRequest, db: Session = Depends(get_db)):
    # 1. Verify start_account_id exists and get its lat/lon
    depot_row = db.execute(
        text("SELECT account_id, latitude, longitude FROM accounts WHERE account_id = :aid"),
        {"aid": request.start_account_id},
    ).fetchone()

    if depot_row is None:
        raise HTTPException(status_code=404, detail=f"Start account {request.start_account_id} not found")

    depot_lat, depot_lon = depot_row.latitude, depot_row.longitude

    # 2. Score all account_ids
    predictor = get_predictor()
    all_scores = predictor.score_accounts(request.account_ids, db)

    if not all_scores:
        raise HTTPException(status_code=404, detail="No scoreable accounts found")

    # 3. Select top_n by priority_score
    selected = all_scores[: request.top_n]

    # 4. Fetch lat/lon for selected accounts
    selected_ids = [s["account_id"] for s in selected]
    placeholders = ", ".join(f":id_{i}" for i in range(len(selected_ids)))
    params = {f"id_{i}": aid for i, aid in enumerate(selected_ids)}

    coord_rows = db.execute(
        text(f"SELECT account_id, latitude, longitude FROM accounts WHERE account_id IN ({placeholders})"),
        params,
    ).fetchall()

    coord_map = {row.account_id: (row.latitude, row.longitude) for row in coord_rows}

    # 5. Build points list: [depot] + [selected account coords]
    #    Exclude start_account_id from visit list to avoid duplicate stops
    points = [(depot_lat, depot_lon)]
    ordered_account_ids = [request.start_account_id]
    for s in selected:
        aid = s["account_id"]
        if aid == request.start_account_id:
            continue  # depot is already point 0
        if aid in coord_map:
            points.append(coord_map[aid])
            ordered_account_ids.append(aid)

    # 6. Solve TSP
    provider = get_provider(request.distance_mode, settings.GOOGLE_MAPS_API_KEY)
    result = solve_tsp(points, provider)

    # 7. Map indices back to account_ids and build route
    route = []
    for stop_idx, point_idx in enumerate(result.ordered_indices):
        aid = ordered_account_ids[point_idx]
        if stop_idx == 0:
            label = "START"
        else:
            label = "ACCOUNT"
        route.append(RouteStop(stop_index=stop_idx, account_id=aid, label=label))

    # Add END (depot repeated at end)
    route.append(RouteStop(
        stop_index=len(route),
        account_id=request.start_account_id,
        label="END",
    ))

    return RouteResponse(
        selected_accounts=selected,
        route=route,
        total_distance_km=result.total_distance_km,
        distance_mode=request.distance_mode,
    )


# --------------- Account CRUD (for frontend) ---------------

@router.get("/v1/accounts", response_model=AccountListResponse)
def list_accounts(db: Session = Depends(get_db)):
    rows = db.execute(
        text("SELECT account_id, account_name, industry, company_size, revenue, region, latitude, longitude FROM accounts ORDER BY account_name")
    ).fetchall()
    accounts = [
        AccountResponse(
            account_id=r.account_id,
            account_name=r.account_name,
            industry=r.industry,
            company_size=r.company_size,
            revenue=r.revenue,
            region=r.region,
            latitude=r.latitude,
            longitude=r.longitude,
        )
        for r in rows
    ]
    return AccountListResponse(accounts=accounts)


@router.get("/v1/accounts/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, db: Session = Depends(get_db)):
    r = db.execute(
        text("SELECT account_id, account_name, industry, company_size, revenue, region, latitude, longitude FROM accounts WHERE account_id = :aid"),
        {"aid": account_id},
    ).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return AccountResponse(
        account_id=r.account_id,
        account_name=r.account_name,
        industry=r.industry,
        company_size=r.company_size,
        revenue=r.revenue,
        region=r.region,
        latitude=r.latitude,
        longitude=r.longitude,
    )


@router.post("/v1/accounts", response_model=AccountResponse, status_code=201)
def create_account(body: AccountCreate, db: Session = Depends(get_db)):
    aid = _hash_id(body.account_name)

    # Check for duplicate
    existing = db.execute(
        text("SELECT account_id FROM accounts WHERE account_id = :aid"),
        {"aid": aid},
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail="Account with this name already exists")

    # Assign coordinates if not provided
    lat, lon = body.latitude, body.longitude
    if lat is None or lon is None:
        lat, lon = assign_coordinates(body.region or "us", aid)

    db.execute(
        text("""
            INSERT INTO accounts (account_id, account_name, industry, company_size, revenue, region, latitude, longitude)
            VALUES (:aid, :name, :industry, :size, :revenue, :region, :lat, :lon)
        """),
        {
            "aid": aid, "name": body.account_name, "industry": body.industry,
            "size": body.company_size, "revenue": body.revenue, "region": body.region,
            "lat": lat, "lon": lon,
        },
    )

    # Insert placeholder opportunity so scoring works
    opp_id = _hash_id(f"{body.account_name}_opp_placeholder")
    db.execute(
        text("""
            INSERT INTO opportunities (opportunity_id, account_id, deal_value, sales_stage, days_since_last_contact, deal_closed)
            VALUES (:oid, :aid, :deal_value, :stage, 0, 0)
            ON CONFLICT (opportunity_id) DO NOTHING
        """),
        {"oid": opp_id, "aid": aid, "deal_value": body.deal_value, "stage": body.sales_stage},
    )

    db.commit()

    return AccountResponse(
        account_id=aid, account_name=body.account_name, industry=body.industry,
        company_size=body.company_size, revenue=body.revenue, region=body.region,
        latitude=lat, longitude=lon,
    )


@router.delete("/v1/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db)):
    existing = db.execute(
        text("SELECT account_id FROM accounts WHERE account_id = :aid"),
        {"aid": account_id},
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Account not found")
    db.execute(text("DELETE FROM opportunities WHERE account_id = :aid"), {"aid": account_id})
    db.execute(text("DELETE FROM accounts WHERE account_id = :aid"), {"aid": account_id})
    db.commit()
