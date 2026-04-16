from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_cid4.documents import load_domain_documents

SUPPORTED_LLM_DOMAINS = (
    "literature",
    "patent",
    "assay",
    "pathway",
    "taxonomy",
    "product_use",
)
SUPPORTED_LLM_FRAMEWORKS = ("pytorch", "tensorflow")
DEFAULT_MODEL_NAME = "cid4_pytorch_gru_lm"
STREAM_EVENT_TYPES = ("start", "token", "complete", "error")


@dataclass(frozen=True)
class LlmServiceError(Exception):
    status_code: int
    code: str
    message: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": "error",
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }


@dataclass(frozen=True)
class TrainingConfig:
    framework: str
    domains: tuple[str, ...]
    output_name: str
    epochs: int
    sequence_length: int
    batch_size: int
    embedding_dim: int
    hidden_size: int
    num_layers: int
    learning_rate: float
    max_chars: int
    seed: int


@dataclass(frozen=True)
class GenerationConfig:
    framework: str
    prompt: str
    model_name: str
    max_new_tokens: int
    temperature: float
    top_k: int
    seed: int | None


@dataclass(frozen=True)
class StreamEvent:
    event: Literal["start", "token", "complete", "error"]
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event, **self.payload}


def sanitize_model_name(model_name: str) -> str:
    cleaned = "".join(character for character in model_name if character.isalnum() or character in {"-", "_"})
    if not cleaned:
        raise LlmServiceError(400, "invalid_model_name", "Model name must contain letters, numbers, '-' or '_'.")
    return cleaned


def build_corpus(domains: tuple[str, ...], max_chars: int) -> tuple[str, dict[str, Any]]:
    unsupported = [domain for domain in domains if domain not in SUPPORTED_LLM_DOMAINS]
    if unsupported:
        raise LlmServiceError(
            400,
            "unsupported_domain",
            f"Unsupported domain selection: {', '.join(sorted(unsupported))}",
        )

    documents = []
    per_domain_counts: dict[str, int] = {}
    for domain in domains:
        domain_documents = load_domain_documents(domain)
        per_domain_counts[domain] = len(domain_documents)
        documents.extend(domain_documents)

    corpus_fragments = []
    for document in documents:
        title = document.title.strip()
        body = document.text_payload.strip()
        fragment = "\n\n".join(part for part in (title, body) if part)
        if fragment:
            corpus_fragments.append(fragment)

    corpus_text = "\n\n<doc>\n\n".join(corpus_fragments)
    if max_chars > 0:
        corpus_text = corpus_text[:max_chars]

    return corpus_text, {
        "domains": list(domains),
        "document_count": len(documents),
        "document_counts_by_domain": per_domain_counts,
        "character_count": len(corpus_text),
        "truncated": len(corpus_text) == max_chars and max_chars > 0,
    }


def artifact_paths(output_dir: Path, framework_prefix: str, model_name: str, checkpoint_suffix: str) -> dict[str, Path]:
    return {
        "checkpoint": output_dir / f"{framework_prefix}_llm_{model_name}{checkpoint_suffix}",
        "metadata": output_dir / f"{framework_prefix}_llm_{model_name}.metadata.json",
    }


def load_metadata_if_available(metadata_path: Path) -> dict[str, Any] | None:
    if not metadata_path.is_file():
        return None
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def build_stream_event(event: Literal["start", "token", "complete", "error"], **payload: Any) -> StreamEvent:
    return StreamEvent(event=event, payload=payload)


def build_error_payload(exc: LlmServiceError, framework: str) -> dict[str, Any]:
    return {
        "framework": framework,
        "error": {
            "code": exc.code,
            "message": exc.message,
        },
    }
