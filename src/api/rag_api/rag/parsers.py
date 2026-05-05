"""LLM response parser registry for model-specific response shapes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ResponseParser(Protocol):
    """Protocol for response parsers."""

    models: list[str]

    def parse(self, response: dict[str, Any]) -> str | None:
        """Parse text from model response."""


@dataclass(frozen=True)
class ClaudeParser:
    """Parser for Claude-on-Bedrock response shapes."""

    models: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.models is None:
            object.__setattr__(self, "models", ["anthropic.claude", "claude"])

    def parse(self, response: dict[str, Any]) -> str | None:
        try:
            content = response.get("output", {}).get("message", {}).get("content")
            if isinstance(content, list):
                texts = [
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                joined = "".join(texts).strip()
                return joined or None
        except Exception:
            return None
        return None


@dataclass(frozen=True)
class TitanParser:
    """Parser for Titan text generation response shapes."""

    models: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.models is None:
            object.__setattr__(self, "models", ["amazon.titan"])

    def parse(self, response: dict[str, Any]) -> str | None:
        results = response.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                text = first.get("outputText")
                if isinstance(text, str) and text.strip():
                    return text.strip()
        completion = response.get("completion")
        if isinstance(completion, str) and completion.strip():
            return completion.strip()
        return None


@dataclass(frozen=True)
class GenericParser:
    """Fallback parser for generic response keys."""

    models: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.models is None:
            object.__setattr__(self, "models", ["*"])

    def parse(self, response: dict[str, Any]) -> str | None:
        try:
            content = response.get("content")
            if isinstance(content, list):
                texts = [
                    c.get("text", "")
                    for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ]
                joined = "".join(texts).strip()
                if joined:
                    return joined
        except Exception:
            pass

        for key in ("text", "completion", "answer", "generated_text"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None


class ParserRegistry:
    """Registry for model-specific response parsers."""

    def __init__(self):
        self._parsers: list[ResponseParser] = []

    def register(self, parser: ResponseParser) -> None:
        self._parsers.append(parser)

    def parse(self, model_id: str, response: dict[str, Any]) -> str | None:
        model_lc = model_id.lower()
        fallback: ResponseParser | None = None

        for parser in self._parsers:
            patterns = [p.lower() for p in parser.models]
            if "*" in patterns:
                fallback = parser
                continue
            if any(pattern in model_lc for pattern in patterns):
                parsed = parser.parse(response)
                if parsed is not None:
                    return parsed

        if fallback is not None:
            return fallback.parse(response)
        return None


def default_parser_registry() -> ParserRegistry:
    registry = ParserRegistry()
    registry.register(ClaudeParser())
    registry.register(TitanParser())
    registry.register(GenericParser())
    return registry
