from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import silhouette_score
from sklearn.naive_bayes import CategoricalNB
from sklearn.neighbors import KNeighborsClassifier, NearestNeighbors
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from ml.common import (
    PreparedDataset,
    build_supervised_split,
    classification_metrics,
    regression_metrics,
)
from ml.datasets import build_taxonomy_clustering_frame


def run_linear_regression(dataset: PreparedDataset) -> dict[str, Any]:
    split = build_supervised_split(dataset, scale_features=False)
    x_train = split.x_train
    y_train = split.y_train.astype(np.float64)
    design_matrix = np.column_stack([np.ones(len(x_train)), x_train])
    manual_coefficients = (
        np.linalg.pinv(design_matrix.T @ design_matrix) @ design_matrix.T @ y_train
    )

    model = LinearRegression()
    model.fit(x_train, y_train)
    predictions = model.predict(split.x_test)

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "manual_normal_equation": {
            "equation": "w = (X^T X)^+ X^T y",
            "intercept": float(manual_coefficients[0]),
            "coefficients": manual_coefficients[1:].astype(float).tolist(),
        },
        "sklearn_linear_regression": {
            "intercept": float(model.intercept_),
            "coefficients": model.coef_.astype(float).tolist(),
        },
        "metrics": regression_metrics(
            split.y_test.astype(np.float64), predictions.astype(np.float64)
        ),
    }


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


def run_svm(dataset: PreparedDataset) -> dict[str, Any]:
    if not has_multiple_classes(dataset):
        return insufficient_class_result(
            dataset, "SVM requires at least two target classes."
        )

    split = build_supervised_split(dataset)
    model = SVC(kernel="rbf", gamma="scale", C=1.0, random_state=42)
    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_test)

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
        "kernel": "rbf",
    }


def run_knn(dataset: PreparedDataset, k_neighbors: int = 3) -> dict[str, Any]:
    if not has_multiple_classes(dataset):
        return insufficient_class_result(
            dataset, "KNN classification requires at least two target classes."
        )

    split = build_supervised_split(dataset)
    neighbor_count = min(k_neighbors, len(split.y_train))
    model = KNeighborsClassifier(n_neighbors=max(1, neighbor_count))
    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_test)

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
        "k_neighbors": int(max(1, neighbor_count)),
    }


def run_atom_neighbor_report(
    dataset: PreparedDataset, query_row_index: int = 0, k_neighbors: int = 4
) -> dict[str, Any]:
    x_values = dataset.feature_matrix()
    neighbor_count = min(max(1, k_neighbors), len(x_values))
    model = NearestNeighbors(n_neighbors=neighbor_count, metric="euclidean")
    model.fit(x_values)
    distances, indices = model.kneighbors(x_values[[query_row_index]])
    query_row = dataset.frame.iloc[query_row_index]

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "query_atom": str(query_row.get("atomLabel", query_row_index)),
        "neighbors": [
            {
                "atom": str(
                    dataset.frame.iloc[int(index)].get("atomLabel", int(index))
                ),
                "distance": float(distance),
            }
            for distance, index in zip(distances[0], indices[0], strict=True)
        ],
    }


def run_decision_tree(dataset: PreparedDataset) -> dict[str, Any]:
    if not has_multiple_classes(dataset):
        return insufficient_class_result(
            dataset,
            "Decision tree classification requires at least two target classes.",
        )

    split = build_supervised_split(dataset, scale_features=False)
    model = DecisionTreeClassifier(max_depth=4, ccp_alpha=0.0, random_state=42)
    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_test)

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
        "feature_importances": {
            feature: float(importance)
            for feature, importance in zip(
                dataset.feature_columns, model.feature_importances_, strict=True
            )
        },
    }


def run_random_forest(dataset: PreparedDataset) -> dict[str, Any]:
    if not has_multiple_classes(dataset):
        return insufficient_class_result(
            dataset,
            "Random forest classification requires at least two target classes.",
        )

    split = build_supervised_split(dataset, scale_features=False)
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=1,
        max_features="sqrt",
        random_state=42,
    )
    model.fit(split.x_train, split.y_train)
    predictions = model.predict(split.x_test)

    importances = sorted(
        (
            {"feature": feature, "importance": float(importance)}
            for feature, importance in zip(
                dataset.feature_columns, model.feature_importances_, strict=True
            )
        ),
        key=lambda item: item["importance"],
        reverse=True,
    )

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
        "feature_importances": importances,
    }


def run_kmeans(atom_frame: pd.DataFrame) -> dict[str, Any]:
    feature_columns = ["atomicNumber", "mass", "bondCount"]
    x_values = atom_frame.loc[:, feature_columns].to_numpy(dtype=np.float64)
    model = KMeans(n_clusters=4, n_init=20, random_state=42)
    labels = model.fit_predict(x_values)
    score = (
        silhouette_score(x_values, labels, sample_size=len(x_values), random_state=42)
        if len(np.unique(labels)) > 1
        else None
    )
    labeled_frame = atom_frame.loc[:, ["atomLabel", "symbol"]].copy()
    labeled_frame["cluster"] = labels

    return {
        "status": "ok",
        "feature_columns": feature_columns,
        "silhouette_score": None if score is None else float(score),
        "cluster_assignments": labeled_frame.to_dict(orient="records"),
        "cluster_centers": model.cluster_centers_.astype(float).tolist(),
    }


def run_hierarchical_clustering() -> dict[str, Any]:
    taxonomy_df = build_taxonomy_clustering_frame()
    x_values = taxonomy_df[["Taxonomy_ID"]].to_numpy(dtype=np.float64)
    linkage_matrix = linkage(x_values, method="ward")
    model = AgglomerativeClustering(n_clusters=2, metric="euclidean", linkage="ward")
    labels = model.fit_predict(x_values)
    labeled_frame = taxonomy_df.copy()
    labeled_frame["cluster"] = labels
    class_breakdown = (
        labeled_frame.groupby(["cluster", "animalClass"])
        .size()
        .rename("count")
        .reset_index()
        .to_dict("records")
    )

    return {
        "status": "ok",
        "row_count": int(len(labeled_frame)),
        "cluster_assignments": labeled_frame.to_dict(orient="records"),
        "class_breakdown": class_breakdown,
        "linkage_preview": linkage_matrix[: min(8, len(linkage_matrix))]
        .astype(float)
        .tolist(),
    }


def run_pca(dataset: PreparedDataset) -> dict[str, Any]:
    x_values = dataset.feature_matrix()
    pipeline = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("pca", PCA(n_components=2, random_state=42)),
        ],
        memory=None,
    )
    transformed = pipeline.fit_transform(x_values)
    model: PCA = pipeline.named_steps["pca"]

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "explained_variance_ratio": model.explained_variance_ratio_.astype(
            float
        ).tolist(),
        "loadings": [
            {
                "feature": feature,
                "pc1": float(model.components_[0, index]),
                "pc2": float(model.components_[1, index]),
            }
            for index, feature in enumerate(dataset.feature_columns)
        ],
        "scores": [
            {
                "row": str(dataset.frame.iloc[index].get("atomLabel", index)),
                "pc1": float(values[0]),
                "pc2": float(values[1]),
            }
            for index, values in enumerate(transformed)
        ],
    }


def run_naive_bayes(dataset: PreparedDataset) -> dict[str, Any]:
    if not has_multiple_classes(dataset):
        return insufficient_class_result(
            dataset, "Naive Bayes classification requires at least two target classes."
        )

    split = build_supervised_split(dataset, scale_features=False)
    x_train = np.rint(split.x_train).astype(int)
    x_test = np.rint(split.x_test).astype(int)
    model = CategoricalNB()
    model.fit(x_train, split.y_train)
    predictions = model.predict(x_test)

    return {
        "status": "ok",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
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
