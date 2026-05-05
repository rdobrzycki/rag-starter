"""LLM invocation and response parsing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..providers.base import LLMProvider
from .parsers import ParserRegistry, default_parser_registry
from .prompt_registry import PromptRegistry, PromptTemplate, default_prompt_registry

if TYPE_CHECKING:
    from ..services.metrics import CloudWatchMetrics


def call_llm(
    llm_provider: LLMProvider,
    model_id: str,
    *,
    question: str,
    context: str,
    prompt_template: str | PromptTemplate = "default",
    prompt_registry: PromptRegistry | None = None,
    parser_registry: ParserRegistry | None = None,
    metrics: "CloudWatchMetrics | None" = None,
) -> str:
    """Invoke the LLM and return plain text.

    Constructs a prompt with system instructions, question, and context,
    then invokes the Bedrock model and extracts the text response.

    Args:
        llm_provider: LLM provider implementation
        model_id: Bedrock model ID to use
        question: User question
        context: Retrieved context chunks
        prompt_template: Prompt template name or instance
        prompt_registry: Optional prompt registry
        parser_registry: Optional parser registry
        metrics: Optional CloudWatch metrics instance

    Returns:
        LLM response text, or string representation of response if parsing fails
    """
    if prompt_registry is None:
        prompt_registry = default_prompt_registry()
    if parser_registry is None:
        parser_registry = default_parser_registry()

    template = (
        prompt_registry.get(prompt_template)
        if isinstance(prompt_template, str)
        else prompt_template
    )
    messages = template.render(question, context)

    resp = llm_provider.invoke(messages, model_id=model_id, temperature=0)
    text = parser_registry.parse(model_id, resp if isinstance(resp, dict) else {})
    return text if text is not None else str(resp)
