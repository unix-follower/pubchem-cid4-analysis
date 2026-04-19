from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

RANDOM_SEED = 42


@dataclass(frozen=True)
class PreparedDataset:
    name: str
    task_type: str
    frame: pd.DataFrame
    feature_columns: list[str]
    target_column: str | None
    description: str
    class_names: list[str] | None = None

    def feature_matrix(self) -> np.ndarray:
        return self.frame.loc[:, self.feature_columns].to_numpy(dtype=np.float64)

    def target_vector(self) -> np.ndarray:
        if self.target_column is None:
            raise ValueError(f"Dataset {self.name} does not define a target column")

        return self.frame[self.target_column].to_numpy()

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "task_type": self.task_type,
            "row_count": int(len(self.frame)),
            "feature_count": int(len(self.feature_columns)),
            "feature_columns": list(self.feature_columns),
            "target_column": self.target_column,
            "class_names": None if self.class_names is None else list(self.class_names),
            "description": self.description,
        }


@dataclass(frozen=True)
class SupervisedSplit:
    x_train: np.ndarray
    x_test: np.ndarray
    y_train: np.ndarray
    y_test: np.ndarray
    scaler: StandardScaler | None
    used_holdout_split: bool
    evaluation_note: str


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)) if len(y_true) > 1 else None,
    }


def classification_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, class_names: list[str] | None
) -> dict[str, Any]:
    labels = None if class_names is None else list(range(len(class_names)))
    confusion = confusion_matrix(y_true, y_pred, labels=labels)

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "confusion_matrix": confusion.astype(int).tolist(),
        "class_names": class_names,
    }


def build_supervised_split(
    dataset: PreparedDataset,
    *,
    test_size: float = 0.3,
    random_state: int = RANDOM_SEED,
    scale_features: bool = True,
) -> SupervisedSplit:
    x_values = dataset.feature_matrix()
    y_values = dataset.target_vector()
    used_holdout_split = can_build_holdout_split(dataset.task_type, y_values)

    if used_holdout_split:
        stratify = y_values if dataset.task_type == "classification" else None
        x_train, x_test, y_train, y_test = train_test_split(
            x_values,
            y_values,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )
        evaluation_note = "Evaluation uses a deterministic holdout split."
    else:
        x_train = x_values
        x_test = x_values
        y_train = y_values
        y_test = y_values
        evaluation_note = "Dataset is too small for a stable holdout split, so evaluation is reported on the training rows."

    scaler = None
    if scale_features:
        scaler = StandardScaler()
        x_train = scaler.fit_transform(x_train)
        x_test = scaler.transform(x_test)

    return SupervisedSplit(
        x_train=x_train,
        x_test=x_test,
        y_train=y_train,
        y_test=y_test,
        scaler=scaler,
        used_holdout_split=used_holdout_split,
        evaluation_note=evaluation_note,
    )


def can_build_holdout_split(task_type: str, y_values: np.ndarray) -> bool:
    if len(y_values) < 8:
        return False

    if task_type != "classification":
        return True

    _, counts = np.unique(y_values, return_counts=True)
    return len(counts) > 1 and int(counts.min()) >= 2
