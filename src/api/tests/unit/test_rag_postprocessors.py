from __future__ import annotations

import pytest

from rag_api.rag.postprocessors import (
    PostprocessorPipeline,
    RefusalDetector,
    ResponseRefusal,
    default_postprocessor_pipeline,
)


class UppercasePostprocessor:
    def process(self, answer: str, sources: list[object], context: str | None) -> str:
        return answer.upper()


class SuffixPostprocessor:
    def process(self, answer: str, sources: list[object], context: str | None) -> str:
        return f"{answer}!"


def test_default_postprocessor_detects_refusal() -> None:
    pipeline = default_postprocessor_pipeline()
    with pytest.raises(ResponseRefusal, match="INSUFFICIENT_INFORMATION"):
        pipeline.process("REFUSE", [], None)


def test_refusal_detector_passes_non_refusal_text() -> None:
    detector = RefusalDetector()
    assert detector.process("answer", [], None) == "answer"


def test_postprocessor_pipeline_runs_in_order() -> None:
    pipeline = PostprocessorPipeline([UppercasePostprocessor(), SuffixPostprocessor()])
    assert pipeline.process("ok", [], None) == "OK!"
