"""Prompt template registry for RAG LLM calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..prompts import SYSTEM_PROMPT


class PromptTemplate(Protocol):
    """Protocol for prompt template implementations."""

    name: str

    def render(self, question: str, context: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Render message payload for model invocation."""


@dataclass(frozen=True)
class DefaultRAGPrompt:
    """Default prompt template matching existing behavior."""

    name: str = "default"

    def render(self, question: str, context: str, **kwargs: Any) -> list[dict[str, Any]]:
        return [
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"QUESTION:\n{question}\n\nCONTEXT:\n{context}",
                    }
                ],
            },
        ]


class PromptRegistry:
    """Registry of named prompt templates."""

    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, template: PromptTemplate) -> None:
        self._templates[template.name] = template

    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            raise KeyError(f"Prompt template not found: {name}")
        return self._templates[name]


def default_prompt_registry() -> PromptRegistry:
    registry = PromptRegistry()
    registry.register(DefaultRAGPrompt())
    return registry
