from typing import Any

import numpy as np
import torch
from torch import nn

from ml.common import (
    PreparedDataset,
    build_supervised_split,
    classification_metrics,
    regression_metrics,
)


def run_torch_classification(dataset: PreparedDataset, epochs: int = 200) -> dict[str, Any]:
    if int(np.unique(dataset.target_vector()).size) < 2:
        return {
            "status": "insufficient_data",
            "library": "pytorch",
            "dataset": dataset.summary(),
            "reason": "PyTorch classification requires at least two target classes.",
        }

    split = build_supervised_split(dataset)
    x_train = torch.tensor(split.x_train, dtype=torch.float32)
    y_train = torch.tensor(split.y_train.astype(np.int64), dtype=torch.long)
    x_eval = torch.tensor(split.x_test, dtype=torch.float32)
    output_dim = len(dataset.class_names or np.unique(split.y_train))
    model = nn.Sequential(
        nn.Linear(x_train.shape[1], 16),
        nn.ReLU(),
        nn.Linear(16, output_dim),
    )
    loss_fn = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=0.0)

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        logits = model(x_train)
        loss = loss_fn(logits, y_train)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        predictions = model(x_eval).argmax(dim=1).cpu().numpy()

    return {
        "library": "pytorch",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "epochs": int(epochs),
        "metrics": classification_metrics(split.y_test, predictions, dataset.class_names),
    }


def run_torch_regression(dataset: PreparedDataset, epochs: int = 300) -> dict[str, Any]:
    split = build_supervised_split(dataset)
    x_train = torch.tensor(split.x_train, dtype=torch.float32)
    y_train = torch.tensor(split.y_train.astype(np.float32).reshape(-1, 1), dtype=torch.float32)
    x_eval = torch.tensor(split.x_test, dtype=torch.float32)
    model = nn.Sequential(
        nn.Linear(x_train.shape[1], 16),
        nn.ReLU(),
        nn.Linear(16, 1),
    )
    loss_fn = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=0.0)

    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        predictions = model(x_train)
        loss = loss_fn(predictions, y_train)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        predictions = model(x_eval).cpu().numpy().reshape(-1)

    return {
        "library": "pytorch",
        "dataset": dataset.summary(),
        "evaluation_note": split.evaluation_note,
        "epochs": int(epochs),
        "metrics": regression_metrics(split.y_test.astype(np.float64), predictions.astype(np.float64)),
    }
