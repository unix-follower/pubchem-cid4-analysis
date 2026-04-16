from __future__ import annotations

import json
import math
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fs_utils import create_dir_if_doesnt_exist
from ml.language_model_common import (
    DEFAULT_MODEL_NAME,
    SUPPORTED_LLM_DOMAINS,
    GenerationConfig,
    LlmServiceError,
    StreamEvent,
    TrainingConfig,
    artifact_paths,
    build_corpus,
    build_stream_event,
    load_metadata_if_available,
    sanitize_model_name,
)

MODEL_FRAMEWORK = "pytorch"


class PyTorchLanguageModelService:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._output_dir = data_dir / "out"
        self._loaded_model_name: str | None = None
        self._loaded_bundle: dict[str, Any] | None = None

    def status(self, model_name: str | None = None) -> dict[str, Any]:
        resolved_name = sanitize_model_name(model_name or DEFAULT_MODEL_NAME)
        metadata = self._load_metadata_if_available(resolved_name)
        availability = self._torch_availability()
        return {
            "status": "ok",
            "framework": MODEL_FRAMEWORK,
            "framework_available": availability["available"],
            "torch_available": availability["available"],
            "torch_reason": availability.get("reason"),
            "model_name": resolved_name,
            "model_available": metadata is not None,
            "supported_domains": list(SUPPORTED_LLM_DOMAINS),
            "artifact_paths": {
                "checkpoint": str(self._checkpoint_path(resolved_name)),
                "metadata": str(self._metadata_path(resolved_name)),
            },
            "model_metadata": metadata,
        }

    def train(self, config: TrainingConfig) -> dict[str, Any]:
        torch_stack = self._require_torch()
        torch = torch_stack["torch"]
        nn = torch_stack["nn"]

        random.seed(config.seed)
        torch.manual_seed(config.seed)

        corpus_text, corpus_stats = build_corpus(config.domains, config.max_chars)
        if len(corpus_text) <= config.sequence_length:
            raise LlmServiceError(
                400,
                "corpus_too_small",
                "The assembled corpus is too small for the requested sequence length.",
            )

        vocabulary = sorted(set(corpus_text))
        if len(vocabulary) < 2:
            raise LlmServiceError(
                400,
                "insufficient_vocabulary",
                "The assembled corpus must contain at least two unique characters.",
            )

        char_to_index = {character: index for index, character in enumerate(vocabulary)}
        encoded = [char_to_index[character] for character in corpus_text]
        max_start = len(encoded) - config.sequence_length - 1
        if max_start < 0:
            raise LlmServiceError(
                400,
                "corpus_too_small",
                "The assembled corpus is too small for the requested sequence length.",
            )

        model = _build_model(
            nn,
            len(vocabulary),
            config.embedding_dim,
            config.hidden_size,
            config.num_layers,
        )
        optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
        loss_fn = nn.CrossEntropyLoss()

        losses: list[float] = []
        model.train()
        for _ in range(config.epochs):
            starts = [random.randint(0, max_start) for _ in range(config.batch_size)]
            inputs = torch.tensor(
                [encoded[start : start + config.sequence_length] for start in starts],
                dtype=torch.long,
            )
            targets = torch.tensor(
                [
                    encoded[start + 1 : start + config.sequence_length + 1]
                    for start in starts
                ],
                dtype=torch.long,
            )

            optimizer.zero_grad()
            logits, _ = model(inputs)
            loss = loss_fn(logits.reshape(-1, len(vocabulary)), targets.reshape(-1))
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))

        checkpoint = {
            "state_dict": model.state_dict(),
            "model_config": {
                "vocab_size": len(vocabulary),
                "embedding_dim": config.embedding_dim,
                "hidden_size": config.hidden_size,
                "num_layers": config.num_layers,
            },
            "vocabulary": vocabulary,
        }

        metadata = {
            "model_name": config.output_name,
            "model_type": "gru-char-language-model",
            "training": {
                "domains": list(config.domains),
                "epochs": config.epochs,
                "sequence_length": config.sequence_length,
                "batch_size": config.batch_size,
                "embedding_dim": config.embedding_dim,
                "hidden_size": config.hidden_size,
                "num_layers": config.num_layers,
                "learning_rate": config.learning_rate,
                "max_chars": config.max_chars,
                "seed": config.seed,
                "final_loss": losses[-1],
                "min_loss": min(losses),
            },
            "corpus": corpus_stats,
            "artifacts": {
                "checkpoint": str(self._checkpoint_path(config.output_name)),
                "metadata": str(self._metadata_path(config.output_name)),
            },
        }

        create_dir_if_doesnt_exist(str(self._output_dir))
        torch.save(checkpoint, self._checkpoint_path(config.output_name))
        self._metadata_path(config.output_name).write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        self._loaded_model_name = None
        self._loaded_bundle = None

        return {
            "status": "ok",
            "framework": MODEL_FRAMEWORK,
            "model_name": config.output_name,
            "model_type": "gru-char-language-model",
            "torch_available": True,
            "corpus": corpus_stats,
            "training": {
                "epochs": config.epochs,
                "sequence_length": config.sequence_length,
                "batch_size": config.batch_size,
                "final_loss": losses[-1],
                "min_loss": min(losses),
                "perplexity_estimate": math.exp(min(losses[-1], 20.0)),
            },
            "artifacts": metadata["artifacts"],
        }

    def generate(self, config: GenerationConfig) -> dict[str, Any]:
        generated_text = "".join(
            event.payload["text"]
            for event in self.stream_generate(config)
            if event.event == "token"
        )
        bundle = self._load_model_bundle(config.model_name)
        metadata = bundle["metadata"]
        prompt = config.prompt.strip()
        return {
            "status": "ok",
            "framework": MODEL_FRAMEWORK,
            "model_name": config.model_name,
            "prompt": prompt,
            "generated_text": prompt + generated_text,
            "generated_suffix": generated_text,
            "generation": {
                "max_new_tokens": config.max_new_tokens,
                "temperature": config.temperature,
                "top_k": config.top_k,
                "seed": config.seed,
            },
            "model_metadata": metadata,
        }

    def stream_generate(self, config: GenerationConfig) -> Iterator[StreamEvent]:
        bundle = self._load_model_bundle(config.model_name)
        torch = bundle["torch"]
        model = bundle["model"]
        char_to_index = bundle["char_to_index"]
        index_to_char = bundle["index_to_char"]
        metadata = bundle["metadata"]

        prompt = config.prompt.strip()
        if not prompt:
            raise LlmServiceError(400, "empty_prompt", "Prompt must not be empty.")
        if config.seed is not None:
            random.seed(config.seed)
            torch.manual_seed(config.seed)

        yield build_stream_event(
            "start",
            framework=MODEL_FRAMEWORK,
            model_name=config.model_name,
            prompt=prompt,
            generation={
                "max_new_tokens": config.max_new_tokens,
                "temperature": config.temperature,
                "top_k": config.top_k,
                "seed": config.seed,
            },
        )

        prompt_indices = [char_to_index.get(character, 0) for character in prompt]
        generated_suffix = ""
        hidden = None

        model.eval()
        with torch.no_grad():
            for token in prompt_indices[:-1]:
                _, hidden = model(torch.tensor([[token]], dtype=torch.long), hidden)

            current_token = prompt_indices[-1]
            for _ in range(config.max_new_tokens):
                logits, hidden = model(
                    torch.tensor([[current_token]], dtype=torch.long), hidden
                )
                next_logits = logits[0, -1]
                next_token = _sample_next_token(
                    torch, next_logits, config.temperature, config.top_k
                )
                chunk = index_to_char[next_token]
                generated_suffix += chunk
                yield build_stream_event(
                    "token",
                    framework=MODEL_FRAMEWORK,
                    model_name=config.model_name,
                    text=chunk,
                    generated_text=prompt + generated_suffix,
                )
                current_token = next_token

        yield build_stream_event(
            "complete",
            framework=MODEL_FRAMEWORK,
            model_name=config.model_name,
            prompt=prompt,
            generated_text=prompt + generated_suffix,
            generated_suffix=generated_suffix,
            model_metadata=metadata,
        )

    def _torch_availability(self) -> dict[str, Any]:
        try:
            import torch
            from torch import nn

            return {"available": True, "torch": torch, "nn": nn}
        except ModuleNotFoundError as exc:
            return {
                "available": False,
                "reason": f"PyTorch is not installed in the current environment: {exc}",
            }

    def _require_torch(self) -> dict[str, Any]:
        availability = self._torch_availability()
        if not availability["available"]:
            raise LlmServiceError(503, "torch_unavailable", str(availability["reason"]))
        return availability

    def _checkpoint_path(self, model_name: str) -> Path:
        return artifact_paths(self._output_dir, MODEL_FRAMEWORK, model_name, ".pt")[
            "checkpoint"
        ]

    def _metadata_path(self, model_name: str) -> Path:
        return artifact_paths(self._output_dir, MODEL_FRAMEWORK, model_name, ".pt")[
            "metadata"
        ]

    def _load_metadata_if_available(self, model_name: str) -> dict[str, Any] | None:
        return load_metadata_if_available(self._metadata_path(model_name))

    def _load_model_bundle(self, model_name: str) -> dict[str, Any]:
        resolved_name = sanitize_model_name(model_name)
        if self._loaded_model_name == resolved_name and self._loaded_bundle is not None:
            return self._loaded_bundle

        torch_stack = self._require_torch()
        torch = torch_stack["torch"]
        nn = torch_stack["nn"]

        checkpoint_path = self._checkpoint_path(resolved_name)
        metadata = self._load_metadata_if_available(resolved_name)
        if not checkpoint_path.is_file() or metadata is None:
            raise LlmServiceError(
                412,
                "model_not_trained",
                f"No trained model artifacts were found for '{resolved_name}'. Train the model first.",
            )

        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        model_config = checkpoint["model_config"]
        index_to_char = list(checkpoint["vocabulary"])
        char_to_index = {
            character: index for index, character in enumerate(index_to_char)
        }
        model = _build_model(
            nn,
            model_config["vocab_size"],
            model_config["embedding_dim"],
            model_config["hidden_size"],
            model_config["num_layers"],
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()

        bundle = {
            "torch": torch,
            "model": model,
            "metadata": metadata,
            "index_to_char": index_to_char,
            "char_to_index": char_to_index,
        }
        self._loaded_model_name = resolved_name
        self._loaded_bundle = bundle
        return bundle


def _build_model(
    nn: Any, vocab_size: int, embedding_dim: int, hidden_size: int, num_layers: int
) -> Any:
    class CharGruLanguageModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, embedding_dim)
            self.gru = nn.GRU(
                embedding_dim, hidden_size, num_layers=num_layers, batch_first=True
            )
            self.output = nn.Linear(hidden_size, vocab_size)

        def forward(self, inputs: Any, hidden: Any = None) -> tuple[Any, Any]:
            embedded = self.embedding(inputs)
            sequence, hidden_state = self.gru(embedded, hidden)
            return self.output(sequence), hidden_state

    return CharGruLanguageModel()


def _sample_next_token(torch: Any, logits: Any, temperature: float, top_k: int) -> int:
    if temperature <= 0:
        return int(torch.argmax(logits).item())

    adjusted_logits = logits / temperature
    if top_k > 0:
        top_values, top_indices = torch.topk(
            adjusted_logits, k=min(top_k, adjusted_logits.shape[-1])
        )
        probabilities = torch.softmax(top_values, dim=-1)
        sampled_index = torch.multinomial(probabilities, num_samples=1)
        return int(top_indices[sampled_index].item())

    probabilities = torch.softmax(adjusted_logits, dim=-1)
    return int(torch.multinomial(probabilities, num_samples=1).item())
