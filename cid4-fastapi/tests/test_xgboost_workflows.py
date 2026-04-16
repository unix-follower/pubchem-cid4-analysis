from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ml.common import PreparedDataset  # noqa: E402
from ml.xgboost_workflows import run_xgboost_classification, run_xgboost_regression  # noqa: E402


class FakeXGBClassifier:
    def __init__(self, **_: object) -> None:
        self.feature_importances_ = np.array([0.7, 0.3], dtype=np.float64)
        self.majority_class = 0

    def fit(self, x_values: np.ndarray, y_values: np.ndarray) -> FakeXGBClassifier:
        del x_values
        self.majority_class = int(np.bincount(y_values.astype(int)).argmax())
        return self

    def predict(self, x_values: np.ndarray) -> np.ndarray:
        return np.full(
            shape=(len(x_values),), fill_value=self.majority_class, dtype=np.int64
        )


class FakeXGBRegressor:
    def __init__(self, **_: object) -> None:
        self.feature_importances_ = np.array([0.6, 0.4], dtype=np.float64)
        self.prediction_value = 0.0

    def fit(self, x_values: np.ndarray, y_values: np.ndarray) -> FakeXGBRegressor:
        del x_values
        self.prediction_value = float(np.mean(y_values.astype(np.float64)))
        return self

    def predict(self, x_values: np.ndarray) -> np.ndarray:
        return np.full(
            shape=(len(x_values),), fill_value=self.prediction_value, dtype=np.float64
        )


class XGBoostWorkflowTests(unittest.TestCase):
    def test_classification_returns_insufficient_data_for_single_class_targets(
        self,
    ) -> None:
        dataset = PreparedDataset(
            name="single-class",
            task_type="classification",
            frame=pd.DataFrame(
                {
                    "feature_a": [0, 1, 2, 3],
                    "feature_b": [1, 1, 1, 1],
                    "target": [1, 1, 1, 1],
                }
            ),
            feature_columns=["feature_a", "feature_b"],
            target_column="target",
            description="Synthetic single-class dataset.",
            class_names=["inactive", "active"],
        )

        result = run_xgboost_classification(dataset)

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["observed_class_count"], 1)

    def test_classification_uses_xgboost_result_shape(self) -> None:
        dataset = PreparedDataset(
            name="binary-classification",
            task_type="classification",
            frame=pd.DataFrame(
                {
                    "feature_a": [0, 1, 2, 3, 4, 5, 6, 7],
                    "feature_b": [1, 0, 1, 0, 1, 0, 1, 0],
                    "target": [0, 0, 1, 1, 0, 1, 0, 1],
                }
            ),
            feature_columns=["feature_a", "feature_b"],
            target_column="target",
            description="Synthetic balanced classification dataset.",
            class_names=["inactive", "active"],
        )

        fake_module = types.SimpleNamespace(XGBClassifier=FakeXGBClassifier)
        with patch.dict(sys.modules, {"xgboost": fake_module}):
            result = run_xgboost_classification(dataset)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["library"], "xgboost")
        self.assertEqual(len(result["feature_importances"]), 2)
        self.assertIn("metrics", result)

    def test_regression_uses_xgboost_result_shape(self) -> None:
        dataset = PreparedDataset(
            name="regression",
            task_type="regression",
            frame=pd.DataFrame(
                {
                    "feature_a": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                    "feature_b": [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
                    "target": [0.2, 0.4, 0.7, 1.0, 1.1, 1.6, 1.9, 2.1, 2.4, 2.8],
                }
            ),
            feature_columns=["feature_a", "feature_b"],
            target_column="target",
            description="Synthetic regression dataset.",
            class_names=None,
        )

        fake_module = types.SimpleNamespace(XGBRegressor=FakeXGBRegressor)
        with patch.dict(sys.modules, {"xgboost": fake_module}):
            result = run_xgboost_regression(dataset)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["library"], "xgboost")
        self.assertEqual(len(result["feature_importances"]), 2)
        self.assertIn("metrics", result)


if __name__ == "__main__":
    unittest.main()
