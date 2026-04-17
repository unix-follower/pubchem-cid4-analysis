from typing import Any

import numpy as np
import tensorflow as tf

from ml.common import (
    PreparedDataset,
    build_supervised_split,
    classification_metrics,
    regression_metrics,
)


def run_tensorflow_regression(dataset: PreparedDataset, epochs: int = 300) -> dict[str, Any]:
    split = build_supervised_split(dataset)
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(split.x_train.shape[1],)),
            tf.keras.layers.Dense(16, activation="relu"),
            tf.keras.layers.Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    model.fit(split.x_train, split.y_train.astype(np.float32), epochs=epochs, verbose=0)
    predictions = model.predict(split.x_test, verbose=0).reshape(-1)

    return {
        "library": "tensorflow",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "epochs": int(epochs),
        "metrics": regression_metrics(split.y_test.astype(np.float64), predictions.astype(np.float64)),
    }


def run_tensorflow_classification(
    dataset: PreparedDataset, epochs: int = 200
) -> dict[str, Any]:
    if int(np.unique(dataset.target_vector()).size) < 2:
        return {
            "status": "insufficient_data",
            "library": "tensorflow",
            "dataset": dataset.summary(),
            "reason": "TensorFlow classification requires at least two target classes.",
        }

    split = build_supervised_split(dataset)
    output_dim = len(dataset.class_names or np.unique(split.y_train))
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(split.x_train.shape[1],)),
            tf.keras.layers.Dense(16, activation="relu"),
            tf.keras.layers.Dense(output_dim, activation="softmax"),
        ]
    )
    model.compile(
        optimizer="adam", loss="sparse_categorical_crossentropy", metrics=["accuracy"]
    )
    model.fit(split.x_train, split.y_train, epochs=epochs, verbose=0)
    predictions = np.argmax(model.predict(split.x_test, verbose=0), axis=1)

    return {
        "status": "ok",
        "library": "tensorflow",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "epochs": int(epochs),
        "metrics": classification_metrics(
            split.y_test, predictions, dataset.class_names
        ),
    }
