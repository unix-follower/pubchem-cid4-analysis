import numpy as np

from .common import PreparedDataset


def ranked_feature_importances(dataset: PreparedDataset, importances: np.ndarray) -> list[dict[str, float | str]]:
    return sorted(
        (
            {"feature": feature, "importance": float(importance)}
            for feature, importance in zip(dataset.feature_columns, importances, strict=True)
        ),
        key=lambda item: float(item["importance"]),
        reverse=True,
    )
