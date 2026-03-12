"""Tests for ML training pipeline and predictor — all use synthetic data, no DB required."""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.ml.train_model import build_preprocessor, train, CATEGORICAL_COLS, NUMERIC_LOG_COLS, NUMERIC_PASS_COLS


def _make_synthetic_df(n=500):
    """Create a synthetic DataFrame mimicking the real CRM data."""
    rng = np.random.RandomState(42)
    industries = ["technology", "medical", "retail", "software", "marketing"]
    regions = ["United States", "Kenya", "Philippines"]
    stages = ["Won", "Lost", "Engaging", "Prospecting"]

    df = pd.DataFrame({
        "industry": rng.choice(industries, n),
        "region": rng.choice(regions, n),
        "sales_stage": rng.choice(stages, n),
        "deal_value": rng.uniform(0, 30000, n),
        "company_size": rng.randint(5, 10000, n),
        "days_since_last_contact": rng.randint(0, 3000, n),
    })
    df["deal_closed"] = (df["sales_stage"] == "Won").astype(int)
    return df


class TestPreprocessor:
    def test_output_shape_expands(self):
        """OHE should expand categorical columns, so output cols > input cols."""
        df = _make_synthetic_df(100)
        feature_cols = CATEGORICAL_COLS + NUMERIC_LOG_COLS + NUMERIC_PASS_COLS
        X = df[feature_cols]
        preprocessor = build_preprocessor()
        X_transformed = preprocessor.fit_transform(X)
        assert X_transformed.shape[1] > len(feature_cols)

    def test_unknown_category_no_crash(self):
        """handle_unknown='ignore' should not crash on unseen categories."""
        df = _make_synthetic_df(100)
        feature_cols = CATEGORICAL_COLS + NUMERIC_LOG_COLS + NUMERIC_PASS_COLS
        preprocessor = build_preprocessor()
        preprocessor.fit(df[feature_cols])

        # Create row with unknown categories
        new_row = pd.DataFrame([{
            "industry": "unknown_sector",
            "region": "Mars",
            "sales_stage": "Negotiating",
            "deal_value": 5000.0,
            "company_size": 100,
            "days_since_last_contact": 30,
        }])
        result = preprocessor.transform(new_row)
        assert result.shape[0] == 1


class TestTraining:
    def test_train_returns_metrics(self):
        """train() should return metrics with AUC in [0, 1] for all splits."""
        df = _make_synthetic_df(500)
        metrics = train(df)
        for split in ["train", "val", "test"]:
            assert f"{split}_auc" in metrics
            assert 0.0 <= metrics[f"{split}_auc"] <= 1.0
            assert f"{split}_accuracy" in metrics
            assert 0.0 <= metrics[f"{split}_accuracy"] <= 1.0

    def test_artifacts_created(self):
        """After training, model.joblib and metrics.json should exist."""
        df = _make_synthetic_df(500)
        train(df)
        artifacts_dir = Path(__file__).parent.parent / "app" / "ml" / "artifacts"
        assert (artifacts_dir / "model.joblib").exists()
        assert (artifacts_dir / "metrics.json").exists()

    def test_metrics_json_structure(self):
        """metrics.json should contain all expected keys."""
        df = _make_synthetic_df(500)
        train(df)
        artifacts_dir = Path(__file__).parent.parent / "app" / "ml" / "artifacts"
        with open(artifacts_dir / "metrics.json") as f:
            metrics = json.load(f)
        expected_keys = {"train_auc", "train_accuracy", "val_auc", "val_accuracy", "test_auc", "test_accuracy"}
        assert expected_keys == set(metrics.keys())


class TestPredictor:
    def test_missing_model_raises(self):
        """Predictor should raise FileNotFoundError if model.joblib doesn't exist."""
        from app.ml.predictor import Predictor
        with pytest.raises(FileNotFoundError):
            Predictor(model_path="/nonexistent/model.joblib")

    def test_score_dataframe_returns_probabilities(self):
        """score_dataframe() should return probabilities in [0, 1]."""
        df = _make_synthetic_df(500)
        train(df)

        from app.ml.predictor import Predictor
        artifacts_dir = Path(__file__).parent.parent / "app" / "ml" / "artifacts"
        predictor = Predictor(model_path=str(artifacts_dir / "model.joblib"))

        test_df = _make_synthetic_df(50)
        feature_cols = CATEGORICAL_COLS + NUMERIC_LOG_COLS + NUMERIC_PASS_COLS
        scores = predictor.score_dataframe(test_df[feature_cols])

        assert len(scores) == 50
        for s in scores:
            assert 0.0 <= s <= 1.0
