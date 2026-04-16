from typing import Any

import numpy as np
import tensorflow as tf

from ml.common import (
    PreparedDataset,
    build_supervised_split,
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
