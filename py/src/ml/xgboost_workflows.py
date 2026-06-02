from typing import Any

import numpy as np
from xgboost import XGBClassifier

from ml.common import (
    PreparedDataset,
    build_supervised_split,
    classification_metrics,
)
from ml.xgboost_utils import ranked_feature_importances


def run_xgboost_classification(dataset: PreparedDataset) -> dict[str, Any]:
    observed_class_count = int(np.unique(dataset.target_vector()).size)
    if observed_class_count < 2:
        return {
            "status": "insufficient_data",
            "library": "xgboost",
            "dataset": dataset.summary(),
            "reason": "XGBoost classification requires at least two target classes.",
            "observed_class_count": observed_class_count,
        }

    split = build_supervised_split(dataset, scale_features=False)
    class_count = int(np.unique(split.y_train).size)
    model_kwargs: dict[str, Any] = {
        "n_estimators": 160,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "random_state": 42,
        "tree_method": "hist",
        "verbosity": 0,
        "eval_metric": "logloss" if class_count <= 2 else "mlogloss",
    }
    if class_count <= 2:
        model_kwargs["objective"] = "binary:logistic"
    else:
        model_kwargs["objective"] = "multi:softprob"
        model_kwargs["num_class"] = class_count

    model = XGBClassifier(**model_kwargs)
    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_test)

    return {
        "status": "ok",
        "library": "xgboost",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(split.y_test, predictions, dataset.class_names),
        "feature_importances": ranked_feature_importances(dataset, model.feature_importances_),
        "model_parameters": {
            "n_estimators": model_kwargs["n_estimators"],
            "max_depth": model_kwargs["max_depth"],
            "learning_rate": model_kwargs["learning_rate"],
            "objective": model_kwargs["objective"],
        },
    }
