from __future__ import annotations

import hashlib
from dataclasses import dataclass
from math import sqrt

from text_processing import (
    BASE_STOPWORDS,
    filter_stopwords,
    lowercase_tokens,
    tokenize_preserving_chemistry,
)


@dataclass(frozen=True)
class HashedTokenEmbeddingProvider:
    dimension: int = 96

    @property
    def name(self) -> str:
        return "hashed-token"

    def embed(self, text: str) -> list[float]:
        if self.dimension <= 0:
            raise ValueError("Embedding dimension must be positive")

        vector = [0.0] * self.dimension
        tokens = self._prepare_tokens(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = (
                int.from_bytes(digest[:8], byteorder="big", signed=False)
                % self.dimension
            )
            sign = -1.0 if digest[8] % 2 else 1.0
            weight = 1.0 + (digest[9] / 255.0)
            vector[bucket] += sign * weight

        norm = sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def _prepare_tokens(self, text: str) -> list[str]:
        lowered = lowercase_tokens(tokenize_preserving_chemistry(text))
        filtered = filter_stopwords(lowered, BASE_STOPWORDS)
        return [token for token in filtered if token and not token.isdigit()]
