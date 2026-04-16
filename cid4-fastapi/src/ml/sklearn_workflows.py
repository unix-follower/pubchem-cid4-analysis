from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from ml.common import (
    PreparedDataset,
    build_supervised_split,
    classification_metrics,
)


def run_logistic_regression(dataset: PreparedDataset) -> dict[str, Any]:
    if not has_multiple_classes(dataset):
        return insufficient_class_result(
            dataset, "Logistic regression requires at least two target classes."
        )

    split = build_supervised_split(dataset)
    model = LogisticRegression(max_iter=2000, random_state=42)
    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_test)

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
        "coefficients": model.coef_.astype(float).tolist(),
        "intercept": model.intercept_.astype(float).tolist(),
    }


def has_multiple_classes(dataset: PreparedDataset) -> bool:
    return int(np.unique(dataset.target_vector()).size) >= 2


def insufficient_class_result(dataset: PreparedDataset, reason: str) -> dict[str, Any]:
    return {
        "status": "insufficient_data",
        "dataset": dataset.summary(),
        "reason": reason,
        "observed_class_count": int(np.unique(dataset.target_vector()).size),
    }
