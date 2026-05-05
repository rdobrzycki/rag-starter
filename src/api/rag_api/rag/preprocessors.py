"""Query preprocessing extension points for RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class QueryPreprocessor(Protocol):
    """Protocol for query preprocessors."""

    def process(self, query: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Process query text and metadata."""


@dataclass(frozen=True)
class QueryLengthValidator:
    """Validates query length limits before RAG execution."""

    min_length: int = 1
    max_length: int = 4000

    def process(self, query: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        size = len(query)
        if size < self.min_length:
            raise ValueError(f"Query must be at least {self.min_length} characters")
        if size > self.max_length:
            raise ValueError(f"Query must be at most {self.max_length} characters")
        return query, metadata


@dataclass(frozen=True)
class QuerySanitizer:
    """Basic query cleanup preprocessor."""

    strip: bool = True

    def process(self, query: str, metadata: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        cleaned = query.replace("\x00", "")
        if self.strip:
            cleaned = cleaned.strip()
        return cleaned, metadata


class PreprocessorPipeline:
    """Ordered query preprocessor pipeline."""

    def __init__(self, preprocessors: list[QueryPreprocessor] | None = None):
        self._preprocessors = preprocessors or []

    def process(
        self, query: str, metadata: dict[str, Any] | None = None
    ) -> tuple[str, dict[str, Any]]:
        out_query = query
        out_metadata = metadata.copy() if metadata else {}

        for preprocessor in self._preprocessors:
            out_query, out_metadata = preprocessor.process(out_query, out_metadata)

        return out_query, out_metadata


def default_preprocessor_pipeline() -> PreprocessorPipeline:
    """Default preprocessor pipeline.

    Default behavior is intentionally no-op for backward compatibility.
    """
    return PreprocessorPipeline([])
