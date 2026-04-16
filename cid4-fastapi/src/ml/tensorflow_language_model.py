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

MODEL_FRAMEWORK = "tensorflow"


class TensorFlowLanguageModelService:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
        self._output_dir = data_dir / "out"
        self._loaded_model_name: str | None = None
        self._loaded_bundle: dict[str, Any] | None = None

    def status(self, model_name: str | None = None) -> dict[str, Any]:
        resolved_name = sanitize_model_name(model_name or DEFAULT_MODEL_NAME)
        metadata = self._load_metadata_if_available(resolved_name)
        availability = self._tensorflow_availability()
        return {
            "status": "ok",
            "framework": MODEL_FRAMEWORK,
            "framework_available": availability["available"],
            "tensorflow_available": availability["available"],
            "tensorflow_reason": availability.get("reason"),
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
        tensorflow_stack = self._require_tensorflow()
        tf = tensorflow_stack["tf"]

        random.seed(config.seed)
        tf.random.set_seed(config.seed)

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
            tf, len(vocabulary), config.embedding_dim, config.hidden_size
        )
        loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)
        optimizer = tf.keras.optimizers.Adam(learning_rate=config.learning_rate)

        losses: list[float] = []
        for _ in range(config.epochs):
            starts = [random.randint(0, max_start) for _ in range(config.batch_size)]
            inputs = tf.convert_to_tensor(
                [encoded[start : start + config.sequence_length] for start in starts],
                dtype=tf.int32,
            )
            targets = tf.convert_to_tensor(
                [
                    encoded[start + 1 : start + config.sequence_length + 1]
                    for start in starts
                ],
                dtype=tf.int32,
            )

            with tf.GradientTape() as tape:
                logits, _ = model(inputs, training=True)
                loss = loss_fn(targets, logits)
            gradients = tape.gradient(loss, model.trainable_variables)
            optimizer.apply_gradients(
                zip(gradients, model.trainable_variables, strict=False)
            )
            losses.append(float(loss.numpy()))

        metadata = {
            "model_name": config.output_name,
            "model_type": "gru-keras-language-model",
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
            "vocabulary": vocabulary,
            "artifacts": {
                "checkpoint": str(self._checkpoint_path(config.output_name)),
                "metadata": str(self._metadata_path(config.output_name)),
            },
        }

        create_dir_if_doesnt_exist(str(self._output_dir))
        model.save(self._checkpoint_path(config.output_name))
        self._metadata_path(config.output_name).write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        self._loaded_model_name = None
        self._loaded_bundle = None

        return {
            "status": "ok",
            "framework": MODEL_FRAMEWORK,
            "model_name": config.output_name,
            "model_type": "gru-keras-language-model",
            "tensorflow_available": True,
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
        tf = bundle["tf"]
        model = bundle["model"]
        vocabulary = bundle["vocabulary"]
        metadata = bundle["metadata"]
        char_to_index = {character: index for index, character in enumerate(vocabulary)}

        prompt = config.prompt.strip()
        if not prompt:
            raise LlmServiceError(400, "empty_prompt", "Prompt must not be empty.")
        if config.seed is not None:
            random.seed(config.seed)
            tf.random.set_seed(config.seed)

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

        embedding_layer = model.get_layer("embedding")
        gru_layer = model.get_layer("gru")
        output_layer = model.get_layer("output")

        prompt_indices = [char_to_index.get(character, 0) for character in prompt]
        generated_suffix = ""
        hidden_state = None

        for token in prompt_indices[:-1]:
            embedded = embedding_layer(tf.convert_to_tensor([[token]], dtype=tf.int32))
            _, hidden_state = gru_layer(
                embedded, initial_state=hidden_state, training=False
            )

        current_token = prompt_indices[-1]
        for _ in range(config.max_new_tokens):
            embedded = embedding_layer(
                tf.convert_to_tensor([[current_token]], dtype=tf.int32)
            )
            sequence, hidden_state = gru_layer(
                embedded, initial_state=hidden_state, training=False
            )
            logits = output_layer(sequence)[0, -1]
            next_token = _sample_next_token(
                tf, logits, config.temperature, config.top_k
            )
            chunk = vocabulary[next_token]
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

    def _tensorflow_availability(self) -> dict[str, Any]:
        try:
            import tensorflow as tf

            return {"available": True, "tf": tf}
        except ModuleNotFoundError as exc:
            return {
                "available": False,
                "reason": f"TensorFlow is not installed in the current environment: {exc}",
            }

    def _require_tensorflow(self) -> dict[str, Any]:
        availability = self._tensorflow_availability()
        if not availability["available"]:
            raise LlmServiceError(
                503, "tensorflow_unavailable", str(availability["reason"])
            )
        return availability

    def _checkpoint_path(self, model_name: str) -> Path:
        return artifact_paths(self._output_dir, MODEL_FRAMEWORK, model_name, ".keras")[
            "checkpoint"
        ]

    def _metadata_path(self, model_name: str) -> Path:
        return artifact_paths(self._output_dir, MODEL_FRAMEWORK, model_name, ".keras")[
            "metadata"
        ]

    def _load_metadata_if_available(self, model_name: str) -> dict[str, Any] | None:
        return load_metadata_if_available(self._metadata_path(model_name))

    def _load_model_bundle(self, model_name: str) -> dict[str, Any]:
        resolved_name = sanitize_model_name(model_name)
        if self._loaded_model_name == resolved_name and self._loaded_bundle is not None:
            return self._loaded_bundle

        tensorflow_stack = self._require_tensorflow()
        tf = tensorflow_stack["tf"]

        checkpoint_path = self._checkpoint_path(resolved_name)
        metadata = self._load_metadata_if_available(resolved_name)
        if not checkpoint_path.is_file() or metadata is None:
            raise LlmServiceError(
                412,
                "model_not_trained",
                f"No trained model artifacts were found for '{resolved_name}'. Train the model first.",
            )

        model = tf.keras.models.load_model(checkpoint_path)
        vocabulary = list(metadata["vocabulary"])
        bundle = {
            "tf": tf,
            "model": model,
            "metadata": metadata,
            "vocabulary": vocabulary,
        }
        self._loaded_model_name = resolved_name
        self._loaded_bundle = bundle
        return bundle


def _build_model(tf: Any, vocab_size: int, embedding_dim: int, hidden_size: int) -> Any:
    inputs = tf.keras.Input(shape=(None,), dtype="int32")
    embedded = tf.keras.layers.Embedding(vocab_size, embedding_dim, name="embedding")(
        inputs
    )
    sequence, state = tf.keras.layers.GRU(
        hidden_size, return_sequences=True, return_state=True, name="gru"
    )(embedded)
    logits = tf.keras.layers.Dense(vocab_size, name="output")(sequence)
    return tf.keras.Model(inputs=inputs, outputs=[logits, state])


def _sample_next_token(tf: Any, logits: Any, temperature: float, top_k: int) -> int:
    if temperature <= 0:
        return int(tf.argmax(logits).numpy())

    adjusted_logits = logits / temperature
    if top_k > 0:
        k = min(top_k, int(adjusted_logits.shape[-1]))
        top_values, top_indices = tf.math.top_k(adjusted_logits, k=k)
        sampled_index = tf.random.categorical(
            tf.expand_dims(top_values, axis=0), num_samples=1
        )
        return int(top_indices[int(sampled_index[0, 0])].numpy())

    sampled = tf.random.categorical(
        tf.expand_dims(adjusted_logits, axis=0), num_samples=1
    )
    return int(sampled[0, 0].numpy())
