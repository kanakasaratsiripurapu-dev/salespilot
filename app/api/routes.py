"""FastAPI route handlers."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    HealthResponse,
    MetaResponse,
    RouteRequest,
    RouteResponse,
    RouteStop,
    ScoreRequest,
    ScoreResponse,
)
from app.core.config import settings
from app.data.data_loader import load_csv
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
