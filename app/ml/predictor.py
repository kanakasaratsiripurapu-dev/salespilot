"""Predictor singleton — loads model.joblib ONCE at startup."""

import logging
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)

_predictor = None


class Predictor:
    def __init__(self, model_path: str | None = None):
        path = Path(model_path or settings.MODEL_PATH)
        if not path.exists():
            raise FileNotFoundError(f"Model not found at {path}")
        self.model = joblib.load(path)
        logger.info("Model loaded from %s", path)

    def score_dataframe(self, df: pd.DataFrame) -> list[float]:
        """Score a pre-built feature DataFrame. Returns list of probabilities."""
        probs = self.model.predict_proba(df)[:, 1]
        return probs.tolist()

    def score_accounts(self, account_ids: list[int], db_session: Session) -> list[dict]:
        """Fetch features from DB and score accounts. Returns sorted list of dicts."""
        if not account_ids:
            return []

        placeholders = ", ".join(f":id_{i}" for i in range(len(account_ids)))
        params = {f"id_{i}": aid for i, aid in enumerate(account_ids)}

        query = text(f"""
            SELECT a.account_id, a.industry, a.company_size, a.region,
                   o.deal_value, o.sales_stage, o.days_since_last_contact
            FROM accounts a
            JOIN opportunities o ON a.account_id = o.account_id
            WHERE a.account_id IN ({placeholders})
        """)

        rows = db_session.execute(query, params).fetchall()
        if not rows:
            return []

        df = pd.DataFrame(rows, columns=[
            "account_id", "industry", "company_size", "region",
            "deal_value", "sales_stage", "days_since_last_contact",
        ])

        feature_cols = ["industry", "region", "sales_stage", "deal_value",
                        "company_size", "days_since_last_contact"]
        probs = self.model.predict_proba(df[feature_cols])[:, 1]
        df["priority_score"] = probs

        # Average score per account (may have multiple opportunities)
        scored = (
            df.groupby("account_id")["priority_score"]
            .mean()
            .reset_index()
            .sort_values("priority_score", ascending=False)
        )

        return [
            {"account_id": int(row.account_id), "priority_score": round(float(row.priority_score), 4)}
            for _, row in scored.iterrows()
        ]


def get_predictor() -> Predictor:
    """Module-level singleton accessor."""
    global _predictor
    if _predictor is None:
        _predictor = Predictor()
    return _predictor


def warm_up() -> bool:
    """Try to load the predictor at startup. Returns True if successful."""
    global _predictor
    try:
        _predictor = Predictor()
        return True
    except FileNotFoundError:
        logger.warning("model.joblib not found — predictor not available until training is run")
        return False
