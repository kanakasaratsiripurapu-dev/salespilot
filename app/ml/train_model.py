"""Train XGBoost classifier to predict deal closure probability.

Usage:
    python -m app.ml.train_model [--csv <csv_dir>]
"""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder
from xgboost import XGBClassifier


ARTIFACTS_DIR = Path(__file__).parent / "artifacts"
CATEGORICAL_COLS = ["industry", "region", "sales_stage"]
NUMERIC_LOG_COLS = ["deal_value"]
NUMERIC_PASS_COLS = ["company_size", "days_since_last_contact"]
LABEL_COL = "deal_closed"


def build_preprocessor() -> ColumnTransformer:
    """Build the sklearn ColumnTransformer for feature preprocessing."""
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_COLS),
            ("log", FunctionTransformer(np.log1p, validate=False), NUMERIC_LOG_COLS),
            ("pass", "passthrough", NUMERIC_PASS_COLS),
        ],
        remainder="drop",
    )


def load_features_from_csv(csv_dir: str) -> pd.DataFrame:
    """Load and merge CSV files into a feature DataFrame."""
    csv_dir = Path(csv_dir)
    accounts = pd.read_csv(csv_dir / "accounts.csv")
    pipeline = pd.read_csv(csv_dir / "sales_pipeline.csv")

    # Rename to match schema
    accounts = accounts.rename(columns={
        "account": "account_name",
        "sector": "industry",
        "employees": "company_size",
        "office_location": "region",
    })
    pipeline = pipeline.rename(columns={
        "account": "account_name",
        "deal_stage": "sales_stage",
        "close_value": "deal_value",
    })

    # Derive deal_closed
    pipeline["deal_closed"] = (pipeline["sales_stage"] == "Won").astype(int)

    # Derive days_since_last_contact
    pipeline["engage_date"] = pd.to_datetime(pipeline["engage_date"], errors="coerce")
    pipeline["close_date"] = pd.to_datetime(pipeline["close_date"], errors="coerce")
    ref = pd.Timestamp.now().normalize()
    last_contact = pipeline["close_date"].fillna(pipeline["engage_date"]).fillna(ref)
    pipeline["days_since_last_contact"] = (ref - last_contact).dt.days.clip(lower=0)

    pipeline["deal_value"] = pipeline["deal_value"].fillna(0.0)

    # Merge with accounts
    df = pipeline.merge(accounts[["account_name", "industry", "company_size", "region"]],
                        on="account_name", how="left")

    # Drop rows missing key features
    df = df.dropna(subset=["industry", "company_size", "region"])

    return df


def load_features_from_db() -> pd.DataFrame:
    """Load features by joining accounts and opportunities in PostgreSQL."""
    from app.db.session import engine

    query = """
        SELECT o.deal_value, o.sales_stage, o.days_since_last_contact, o.deal_closed,
               a.industry, a.company_size, a.region
        FROM opportunities o
        JOIN accounts a ON o.account_id = a.account_id
    """
    df = pd.read_sql(query, engine)
    return df


def train(df: pd.DataFrame) -> dict:
    """Train XGBoost on the given feature DataFrame. Returns metrics dict."""
    feature_cols = CATEGORICAL_COLS + NUMERIC_LOG_COLS + NUMERIC_PASS_COLS
    X = df[feature_cols].copy()
    y = df[LABEL_COL].values

    # Stratified 70/15/15 split
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42
    )

    # Auto scale_pos_weight for class imbalance
    neg_count = (y_train == 0).sum()
    pos_count = (y_train == 1).sum()
    scale_pos_weight = neg_count / pos_count if pos_count > 0 else 1.0

    preprocessor = build_preprocessor()

    model = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            eval_metric="logloss",
        )),
    ])

    model.fit(X_train, y_train)

    # Evaluate on all splits
    metrics = {}
    for name, X_split, y_split in [
        ("train", X_train, y_train),
        ("val", X_val, y_val),
        ("test", X_test, y_test),
    ]:
        y_prob = model.predict_proba(X_split)[:, 1]
        y_pred = model.predict(X_split)
        auc = roc_auc_score(y_split, y_prob)
        acc = accuracy_score(y_split, y_pred)
        metrics[f"{name}_auc"] = round(auc, 4)
        metrics[f"{name}_accuracy"] = round(acc, 4)

    # Save artifacts
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = ARTIFACTS_DIR / "model.joblib"
    metrics_path = ARTIFACTS_DIR / "metrics.json"

    joblib.dump(model, model_path)
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Model saved to {model_path}")
    print(f"Metrics: {json.dumps(metrics, indent=2)}")

    return metrics


def main():
    parser = argparse.ArgumentParser(description="Train SalesPilot XGBoost model")
    parser.add_argument("--csv", type=str, default=None, help="Path to CSV directory")
    args = parser.parse_args()

    if args.csv:
        print(f"Loading features from CSV: {args.csv}")
        df = load_features_from_csv(args.csv)
    else:
        print("Loading features from database")
        df = load_features_from_db()

    print(f"Training on {len(df)} samples")
    print(f"Class balance: {df[LABEL_COL].value_counts().to_dict()}")
    train(df)


if __name__ == "__main__":
    main()
