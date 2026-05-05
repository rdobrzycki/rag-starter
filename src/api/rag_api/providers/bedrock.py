"""Bedrock-backed provider implementations."""

from __future__ import annotations

from typing import Any

from ..bedrock import Bedrock

ANTHROPIC_VERSION = "bedrock-2023-05-31"
DEFAULT_MAX_TOKENS = 1024


def _is_anthropic_model(model_id: str) -> bool:
    model_lc = model_id.lower()
    return "anthropic." in model_lc or "claude" in model_lc


def _normalize_content(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, list):
        return [item for item in content if isinstance(item, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [{"type": "text", "text": str(content)}]


def _extract_system_text(content: Any) -> str:
    texts = [
        block.get("text", "").strip()
        for block in _normalize_content(content)
        if block.get("type") == "text"
    ]
    return "\n\n".join(text for text in texts if text)


def _build_anthropic_payload(messages: list[dict[str, Any]], temperature: float) -> dict[str, Any]:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, Any]] = []

    for message in messages:
        role = str(message.get("role", "user"))
        content = message.get("content", [])

        if role == "system":
            system_text = _extract_system_text(content)
            if system_text:
                system_parts.append(system_text)
            continue

        anthropic_messages.append(
            {
                "role": role if role in {"user", "assistant"} else "user",
                "content": _normalize_content(content),
            }
        )

    payload: dict[str, Any] = {
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "messages": anthropic_messages,
        "temperature": temperature,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    return payload


class BedrockEmbedding:
    """Embedding provider backed by Bedrock runtime."""

    def __init__(self, bedrock: Bedrock):
        self._bedrock = bedrock

    def embed(self, text: str, *, model_id: str) -> list[float]:
        return self._bedrock.embed(model_id, text)


class BedrockLLM:
    """LLM provider backed by Bedrock runtime."""

    def __init__(self, bedrock: Bedrock):
        self._bedrock = bedrock

    def invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        model_id: str,
        temperature: float = 0,
    ) -> dict[str, Any]:
        if _is_anthropic_model(model_id):
            payload = _build_anthropic_payload(messages, temperature)
        else:
            payload = {
                "messages": messages,
                "temperature": temperature,
            }
        return self._bedrock.invoke(model_id, payload)
