from __future__ import annotations

import pytest

from rag_api.rag.preprocessors import (
    PreprocessorPipeline,
    QueryLengthValidator,
    QuerySanitizer,
    default_preprocessor_pipeline,
)


class AddMetadataPreprocessor:
    def process(self, query: str, metadata: dict[str, object]) -> tuple[str, dict[str, object]]:
        out = dict(metadata)
        out["seen"] = True
        return f"{query}!", out


def test_default_preprocessor_pipeline_is_noop() -> None:
    pipeline = default_preprocessor_pipeline()
    query, metadata = pipeline.process("hello", {"a": 1})
    assert query == "hello"
    assert metadata == {"a": 1}


def test_query_length_validator_rejects_long_query() -> None:
    validator = QueryLengthValidator(max_length=5)
    with pytest.raises(ValueError, match="at most"):
        validator.process("too long", {})


def test_query_sanitizer_strips_whitespace_and_nul() -> None:
    sanitizer = QuerySanitizer()
    query, metadata = sanitizer.process("  hi\x00there  ", {"k": "v"})
    assert query == "hithere"
    assert metadata == {"k": "v"}


def test_preprocessor_pipeline_runs_in_order() -> None:
    pipeline = PreprocessorPipeline([AddMetadataPreprocessor(), AddMetadataPreprocessor()])
    query, metadata = pipeline.process("q", {})
    assert query == "q!!"
    assert metadata["seen"] is True
