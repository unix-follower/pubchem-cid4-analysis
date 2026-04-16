from typing import Any

import numpy as np
from xgboost import XGBRegressor

from ml.common import (
    PreparedDataset,
    build_supervised_split,
    regression_metrics,
)


def run_xgboost_regression(dataset: PreparedDataset) -> dict[str, Any]:
    split = build_supervised_split(dataset, scale_features=False)
    model_kwargs: dict[str, Any] = {
        "n_estimators": 220,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "random_state": 42,
        "tree_method": "hist",
        "verbosity": 0,
        "objective": "reg:squarederror",
    }
    model = XGBRegressor(**model_kwargs)
    model.fit(split.x_train, split.y_train.astype(np.float64))
    predictions = model.predict(split.x_test)

    return {
        "library": "xgboost",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": regression_metrics(split.y_test.astype(np.float64), predictions.astype(np.float64)),
        "feature_importances": ranked_feature_importances(dataset, model.feature_importances_),
        "model_parameters": {
            "n_estimators": model_kwargs["n_estimators"],
            "max_depth": model_kwargs["max_depth"],
            "learning_rate": model_kwargs["learning_rate"],
            "objective": model_kwargs["objective"],
        },
    }


def ranked_feature_importances(dataset: PreparedDataset, importances: np.ndarray) -> list[dict[str, float | str]]:
    return sorted(
        (
            {"feature": feature, "importance": float(importance)}
            for feature, importance in zip(dataset.feature_columns, importances, strict=True)
        ),
        key=lambda item: float(item["importance"]),
        reverse=True,
    )
