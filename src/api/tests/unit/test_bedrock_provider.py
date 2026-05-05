from __future__ import annotations

from rag_api.providers.bedrock import BedrockLLM


class StubBedrock:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def invoke(self, model_id: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append((model_id, payload))
        return {"ok": True}


def test_bedrock_llm_formats_anthropic_messages_payload() -> None:
    bedrock = StubBedrock()
    provider = BedrockLLM(bedrock)  # type: ignore[arg-type]

    messages = [
        {"role": "system", "content": [{"type": "text", "text": "system prompt"}]},
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
    ]

    provider.invoke(
        messages,
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        temperature=0.2,
    )

    _, payload = bedrock.calls[0]
    assert payload["anthropic_version"] == "bedrock-2023-05-31"
    assert payload["max_tokens"] == 1024
    assert payload["system"] == "system prompt"
    assert payload["temperature"] == 0.2
    assert payload["messages"] == [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]


def test_bedrock_llm_keeps_generic_payload_for_non_anthropic_models() -> None:
    bedrock = StubBedrock()
    provider = BedrockLLM(bedrock)  # type: ignore[arg-type]

    messages = [{"role": "user", "content": [{"type": "text", "text": "hello"}]}]

    provider.invoke(messages, model_id="amazon.nova-pro-v1:0", temperature=0)

    _, payload = bedrock.calls[0]
    assert payload == {"messages": messages, "temperature": 0}
