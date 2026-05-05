"""Response postprocessing extension points for RAG."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ResponseRefusal(Exception):
    """Signal from postprocessors that the answer must be refused."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class ResponsePostprocessor(Protocol):
    """Protocol for response postprocessors."""

    def process(self, answer: str, sources: list[Any], context: str | None) -> str:
        """Process LLM answer text and return final answer text."""


@dataclass(frozen=True)
class RefusalDetector:
    """Detects model refusals in generated text."""

    refusal_token: str = "REFUSE"
    reason: str = "INSUFFICIENT_INFORMATION"

    def process(self, answer: str, sources: list[Any], context: str | None) -> str:
        if self.refusal_token in answer:
            raise ResponseRefusal(self.reason)
        return answer


class PostprocessorPipeline:
    """Ordered response postprocessor pipeline."""

    def __init__(self, postprocessors: list[ResponsePostprocessor] | None = None):
        self._postprocessors = postprocessors or []

    def process(self, answer: str, sources: list[Any], context: str | None) -> str:
        out_answer = answer
        for postprocessor in self._postprocessors:
            out_answer = postprocessor.process(out_answer, sources, context)
        return out_answer


def default_postprocessor_pipeline() -> PostprocessorPipeline:
    """Default pipeline preserving existing refusal behavior."""
    return PostprocessorPipeline([RefusalDetector()])
