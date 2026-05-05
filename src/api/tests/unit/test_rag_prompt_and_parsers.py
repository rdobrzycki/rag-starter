from __future__ import annotations

import pytest

from rag_api.rag.llm import call_llm
from rag_api.rag.parsers import default_parser_registry
from rag_api.rag.prompt_registry import DefaultRAGPrompt, PromptRegistry, default_prompt_registry


class MockLLMProvider:
    def __init__(self, response: dict[str, object]):
        self.response = response
        self.calls: list[tuple[list[dict[str, object]], str]] = []

    def invoke(
        self,
        messages: list[dict[str, object]],
        *,
        model_id: str,
        temperature: float = 0,
    ) -> dict[str, object]:
        self.calls.append((messages, model_id))
        return self.response


class JsonPromptTemplate:
    name = "json"

    def render(self, question: str, context: str, **kwargs: object) -> list[dict[str, object]]:
        return [{"role": "user", "content": [{"type": "text", "text": f"{question}|{context}"}]}]


def test_default_prompt_registry_has_default_template() -> None:
    registry = default_prompt_registry()
    template = registry.get("default")
    messages = template.render("Q", "C")
    assert len(messages) == 2
    assert messages[0]["role"] == "system"


def test_prompt_registry_raises_for_unknown_template() -> None:
    registry = PromptRegistry()
    registry.register(DefaultRAGPrompt())
    with pytest.raises(KeyError):
        registry.get("missing")


def test_parser_registry_parses_claude_shape() -> None:
    registry = default_parser_registry()
    response = {
        "output": {
            "message": {
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "text", "text": " world"},
                ]
            }
        }
    }
    assert registry.parse("anthropic.claude-3-sonnet", response) == "hello world"


def test_parser_registry_uses_generic_fallback() -> None:
    registry = default_parser_registry()
    assert registry.parse("unknown.model", {"text": "ok"}) == "ok"


def test_call_llm_uses_prompt_and_parser_registries() -> None:
    prompt_registry = PromptRegistry()
    prompt_registry.register(DefaultRAGPrompt())
    prompt_registry.register(JsonPromptTemplate())

    parser_registry = default_parser_registry()

    provider = MockLLMProvider({"text": "parsed"})

    out = call_llm(
        provider,
        "custom-model",
        question="What?",
        context="Ctx",
        prompt_template="json",
        prompt_registry=prompt_registry,
        parser_registry=parser_registry,
    )

    assert out == "parsed"
    messages, model_id = provider.calls[0]
    assert model_id == "custom-model"
    assert "What?|Ctx" in str(messages)
