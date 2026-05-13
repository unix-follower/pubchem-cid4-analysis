from typing import Literal
from pydantic import BaseModel, Field

from src.ml.language_model_common import (
    DEFAULT_MODEL_NAME,
    SUPPORTED_LLM_DOMAINS,
)


class TrainLanguageModelRequest(BaseModel):
    framework: Literal["pytorch", "tensorflow"] = Field(default="pytorch")
    domains: list[str] = Field(default_factory=lambda: list(SUPPORTED_LLM_DOMAINS))
    output_name: str = Field(
        default=DEFAULT_MODEL_NAME,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    epochs: int = Field(default=12, ge=1, le=200)
    sequence_length: int = Field(default=64, ge=8, le=256)
    batch_size: int = Field(default=32, ge=1, le=256)
    embedding_dim: int = Field(default=64, ge=8, le=256)
    hidden_size: int = Field(default=128, ge=16, le=512)
    num_layers: int = Field(default=1, ge=1, le=4)
    learning_rate: float = Field(default=0.003, gt=0.0, le=0.1)
    max_chars: int = Field(default=120000, ge=1024, le=500000)
    seed: int = Field(default=17, ge=0, le=2_147_483_647)


class GenerateLanguageModelRequest(BaseModel):
    framework: Literal["pytorch", "tensorflow"] = Field(default="pytorch")
    prompt: str = Field(min_length=1, max_length=4000)
    model_name: str = Field(
        default=DEFAULT_MODEL_NAME,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    max_new_tokens: int = Field(default=160, ge=1, le=1000)
    temperature: float = Field(default=0.8, ge=0.0, le=5.0)
    top_k: int = Field(default=8, ge=0, le=128)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
