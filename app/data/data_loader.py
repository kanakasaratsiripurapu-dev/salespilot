"""Load CRM CSV data into PostgreSQL — full 4-table pipeline.

Reads accounts.csv, products.csv, sales_teams.csv, and sales_pipeline.csv,
normalises columns, derives missing fields, generates synthetic geo
coordinates, and bulk-upserts into DB.

Usage:
    python -m app.data.data_loader <csv_dir>
"""

import hashlib
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.data.synthetic_geo import enrich_dataframe
from app.db.session import engine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hashing helpers — deterministic int64 IDs from string keys
# ---------------------------------------------------------------------------

def _hash_id(value: str) -> int:
    """Generate a stable positive int64 from a string (JS-safe range)."""
    h = int(hashlib.sha256(value.strip().lower().encode()).hexdigest(), 16)
    return h % (2**53)


# ---------------------------------------------------------------------------
# Per-table loaders
# ---------------------------------------------------------------------------

def _load_accounts(csv_dir: Path) -> pd.DataFrame:
    """Load accounts.csv → DataFrame ready for DB insert."""
    path = csv_dir / "accounts.csv"
    if not path.exists():
        raise FileNotFoundError(f"accounts.csv not found in {csv_dir}")

    df = pd.read_csv(path)
    df = df.rename(columns={
        "account": "account_name",
        "sector": "industry",
        "employees": "company_size",
        "office_location": "region",
    })

    df["account_id"] = df["account_name"].apply(_hash_id)

    # Preserve extra columns from the CSV
    df["revenue"] = pd.to_numeric(df.get("revenue"), errors="coerce")
    df["year_established"] = pd.to_numeric(df.get("year_established"), errors="coerce").astype("Int64")
    df["subsidiary_of"] = df.get("subsidiary_of", pd.Series(dtype=str))

    # Synthetic geo
    df["latitude"] = np.nan
    df["longitude"] = np.nan
    enrich_dataframe(df)

    cols = [
        "account_id", "account_name", "industry", "company_size",
        "revenue", "year_established", "region", "subsidiary_of",
        "latitude", "longitude",
    ]
    return df[cols]


def _load_products(csv_dir: Path) -> pd.DataFrame:
    """Load products.csv → DataFrame ready for DB insert."""
    path = csv_dir / "products.csv"
    if not path.exists():
        raise FileNotFoundError(f"products.csv not found in {csv_dir}")

    df = pd.read_csv(path)
    df = df.rename(columns={"product": "product_name"})
    df["product_id"] = df["product_name"].apply(_hash_id)
    df["sales_price"] = pd.to_numeric(df["sales_price"], errors="coerce")

    return df[["product_id", "product_name", "series", "sales_price"]]


def _load_sales_teams(csv_dir: Path) -> pd.DataFrame:
    """Load sales_teams.csv → DataFrame ready for DB insert."""
    path = csv_dir / "sales_teams.csv"
    if not path.exists():
        raise FileNotFoundError(f"sales_teams.csv not found in {csv_dir}")

    df = pd.read_csv(path)
    df["agent_id"] = df["sales_agent"].apply(_hash_id)

    return df[["agent_id", "sales_agent", "manager", "regional_office"]]


def _load_opportunities(
    csv_dir: Path,
    account_lookup: dict[str, int],
    agent_lookup: dict[str, int],
    product_lookup: dict[str, int],
) -> pd.DataFrame:
    """Load sales_pipeline.csv → DataFrame ready for DB insert.

    Requires lookup dicts (name → id) for the three foreign key tables.
    """
    path = csv_dir / "sales_pipeline.csv"
    if not path.exists():
        raise FileNotFoundError(f"sales_pipeline.csv not found in {csv_dir}")

    df = pd.read_csv(path)
    df = df.rename(columns={
        "account": "account_name",
        "deal_stage": "sales_stage",
        "close_value": "deal_value",
    })

    # Deterministic opportunity_id
    df["opportunity_id"] = df["opportunity_id"].apply(
        lambda x: _hash_id(str(x).strip())
    )

    # FK lookups (case-insensitive)
    df["account_id"] = df["account_name"].str.strip().str.lower().map(account_lookup)
    df["agent_id"] = df["sales_agent"].str.strip().str.lower().map(agent_lookup)
    df["product_id"] = df["product"].str.strip().str.lower().map(product_lookup)

    # Derive deal_closed
    df["deal_closed"] = (df["sales_stage"] == "Won").astype(int)

    # Parse dates
    df["engage_date"] = pd.to_datetime(df["engage_date"], errors="coerce")
    df["close_date"] = pd.to_datetime(df["close_date"], errors="coerce")

    # Derive days_since_last_contact
    reference_date = pd.Timestamp(datetime.now().date())
    last_contact = df["close_date"].fillna(df["engage_date"]).fillna(reference_date)
    df["days_since_last_contact"] = (reference_date - last_contact).dt.days.clip(lower=0)

    # Clean up
    df = df.dropna(subset=["account_id"])
    df["account_id"] = df["account_id"].astype(int)
    df["agent_id"] = df["agent_id"].astype("Int64")   # nullable int
    df["product_id"] = df["product_id"].astype("Int64")
    df["deal_value"] = df["deal_value"].fillna(0.0)

    cols = [
        "opportunity_id", "account_id", "agent_id", "product_id",
        "deal_value", "sales_stage", "engage_date", "close_date",
        "days_since_last_contact", "deal_closed",
    ]
    return df[cols]


# ---------------------------------------------------------------------------
# Bulk upsert helpers
# ---------------------------------------------------------------------------

def _upsert_accounts(conn, df: pd.DataFrame) -> None:
    """Bulk upsert accounts using a temp table + INSERT … ON CONFLICT."""
    conn.execute(text("CREATE TEMP TABLE _tmp_accounts (LIKE accounts INCLUDING DEFAULTS) ON COMMIT DROP"))
    rows = df.where(df.notna(), None).to_dict("records")
    conn.execute(
        text("""
            INSERT INTO _tmp_accounts
                (account_id, account_name, industry, company_size,
                 revenue, year_established, region, subsidiary_of,
                 latitude, longitude)
            VALUES
                (:account_id, :account_name, :industry, :company_size,
                 :revenue, :year_established, :region, :subsidiary_of,
                 :latitude, :longitude)
        """),
        rows,
    )
    conn.execute(text("""
        INSERT INTO accounts
            (account_id, account_name, industry, company_size,
             revenue, year_established, region, subsidiary_of,
             latitude, longitude)
        SELECT account_id, account_name, industry, company_size,
               revenue, year_established, region, subsidiary_of,
               latitude, longitude
        FROM _tmp_accounts
        ON CONFLICT (account_id) DO UPDATE SET
            account_name = EXCLUDED.account_name,
            industry     = EXCLUDED.industry,
            company_size = EXCLUDED.company_size,
            revenue      = EXCLUDED.revenue,
            year_established = EXCLUDED.year_established,
            region       = EXCLUDED.region,
            subsidiary_of = EXCLUDED.subsidiary_of,
            latitude     = EXCLUDED.latitude,
            longitude    = EXCLUDED.longitude
    """))


def _upsert_products(conn, df: pd.DataFrame) -> None:
    conn.execute(text("CREATE TEMP TABLE _tmp_products (LIKE products INCLUDING DEFAULTS) ON COMMIT DROP"))
    rows = df.where(df.notna(), None).to_dict("records")
    conn.execute(
        text("""
            INSERT INTO _tmp_products (product_id, product_name, series, sales_price)
            VALUES (:product_id, :product_name, :series, :sales_price)
        """),
        rows,
    )
    conn.execute(text("""
        INSERT INTO products (product_id, product_name, series, sales_price)
        SELECT product_id, product_name, series, sales_price
        FROM _tmp_products
        ON CONFLICT (product_id) DO UPDATE SET
            product_name = EXCLUDED.product_name,
            series       = EXCLUDED.series,
            sales_price  = EXCLUDED.sales_price
    """))


def _upsert_sales_teams(conn, df: pd.DataFrame) -> None:
    conn.execute(text("CREATE TEMP TABLE _tmp_teams (LIKE sales_teams INCLUDING DEFAULTS) ON COMMIT DROP"))
    rows = df.where(df.notna(), None).to_dict("records")
    conn.execute(
        text("""
            INSERT INTO _tmp_teams (agent_id, sales_agent, manager, regional_office)
            VALUES (:agent_id, :sales_agent, :manager, :regional_office)
        """),
        rows,
    )
    conn.execute(text("""
        INSERT INTO sales_teams (agent_id, sales_agent, manager, regional_office)
        SELECT agent_id, sales_agent, manager, regional_office
        FROM _tmp_teams
        ON CONFLICT (agent_id) DO UPDATE SET
            sales_agent    = EXCLUDED.sales_agent,
            manager        = EXCLUDED.manager,
            regional_office = EXCLUDED.regional_office
    """))


def _upsert_opportunities(conn, df: pd.DataFrame) -> None:
    conn.execute(text("CREATE TEMP TABLE _tmp_opps (LIKE opportunities INCLUDING DEFAULTS) ON COMMIT DROP"))
    rows = df.where(df.notna(), None).to_dict("records")
    # Convert dates to strings for parameterised insert; NaT → None
    for r in rows:
        for col in ("engage_date", "close_date"):
            val = r[col]
            if val is None or (hasattr(val, "isoformat") and pd.isna(val)):
                r[col] = None
            elif hasattr(val, "isoformat"):
                r[col] = val.isoformat()
            elif isinstance(val, str) and val == "NaT":
                r[col] = None
    conn.execute(
        text("""
            INSERT INTO _tmp_opps
                (opportunity_id, account_id, agent_id, product_id,
                 deal_value, sales_stage, engage_date, close_date,
                 days_since_last_contact, deal_closed)
            VALUES
                (:opportunity_id, :account_id, :agent_id, :product_id,
                 :deal_value, :sales_stage, :engage_date, :close_date,
                 :days_since_last_contact, :deal_closed)
        """),
        rows,
    )
    conn.execute(text("""
        INSERT INTO opportunities
            (opportunity_id, account_id, agent_id, product_id,
             deal_value, sales_stage, engage_date, close_date,
             days_since_last_contact, deal_closed)
        SELECT opportunity_id, account_id, agent_id, product_id,
               deal_value, sales_stage, engage_date, close_date,
               days_since_last_contact, deal_closed
        FROM _tmp_opps
        ON CONFLICT (opportunity_id) DO UPDATE SET
            account_id   = EXCLUDED.account_id,
            agent_id     = EXCLUDED.agent_id,
            product_id   = EXCLUDED.product_id,
            deal_value   = EXCLUDED.deal_value,
            sales_stage  = EXCLUDED.sales_stage,
            engage_date  = EXCLUDED.engage_date,
            close_date   = EXCLUDED.close_date,
            days_since_last_contact = EXCLUDED.days_since_last_contact,
            deal_closed  = EXCLUDED.deal_closed
    """))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_schema() -> None:
    """Create all tables from schema.sql if they don't exist."""
    schema_path = Path(__file__).parent.parent / "db" / "schema.sql"
    sql = schema_path.read_text()
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    logger.info("Schema initialised.")


def load_csv(csv_dir: str) -> dict[str, int]:
    """Load all CSVs from the given directory into PostgreSQL.

    Returns a dict with row counts per table.
    """
    csv_dir = Path(csv_dir)

    # 1. Load reference tables first (no FK deps)
    acct_df = _load_accounts(csv_dir)
    prod_df = _load_products(csv_dir)
    team_df = _load_sales_teams(csv_dir)

    # 2. Build FK lookup dicts (lowercase name → id)
    account_lookup = dict(zip(
        acct_df["account_name"].str.strip().str.lower(),
        acct_df["account_id"],
    ))
    agent_lookup = dict(zip(
        team_df["sales_agent"].str.strip().str.lower(),
        team_df["agent_id"],
    ))
    product_lookup = dict(zip(
        prod_df["product_name"].str.strip().str.lower(),
        prod_df["product_id"],
    ))

    # 3. Load opportunities with FK resolution
    opp_df = _load_opportunities(csv_dir, account_lookup, agent_lookup, product_lookup)

    # 4. Ensure schema exists
    init_schema()

    # 5. Bulk upsert in dependency order
    with engine.begin() as conn:
        _upsert_accounts(conn, acct_df)
        _upsert_products(conn, prod_df)
        _upsert_sales_teams(conn, team_df)
        _upsert_opportunities(conn, opp_df)

    counts = {
        "accounts": len(acct_df),
        "products": len(prod_df),
        "sales_teams": len(team_df),
        "opportunities": len(opp_df),
    }
    logger.info("Pipeline complete: %s", counts)
    print(f"Loaded {counts} into PostgreSQL.")
    return counts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m app.data.data_loader <csv_dir>")
        sys.exit(1)
    load_csv(sys.argv[1])
