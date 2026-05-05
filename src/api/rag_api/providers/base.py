"""Provider abstraction protocols for RAG."""

from __future__ import annotations

from typing import Any, Protocol


class EmbeddingProvider(Protocol):
    """Embedding provider abstraction."""

    def embed(self, text: str, *, model_id: str) -> list[float]:
        """Embed a text string into a vector."""


class LLMProvider(Protocol):
    """LLM invocation provider abstraction."""

    def invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        model_id: str,
        temperature: float = 0,
    ) -> dict[str, Any]:
        """Invoke model and return raw provider response."""
