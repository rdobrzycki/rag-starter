"""CLI entrypoint for RAG efficiency testing. Outputs JSON and optional PoV report."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from .reporter import build_report, render_pov, write_json

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TEST_CASES_PATH = FIXTURES_DIR / "test_cases.json"


def load_test_cases() -> list[dict]:
    """Load test cases from fixtures/test_cases.json."""
    with TEST_CASES_PATH.open() as f:
        return json.load(f)


def query_api(client: httpx.Client, query: str) -> dict:
    """POST /query with return_context; return JSON."""
    r = client.post("/query", json={"query": query, "return_context": True})
    r.raise_for_status()
    return r.json()


def run_quality(
    client: httpx.Client, test_cases: list[dict], max_cases: int = 15
) -> dict[str, float]:
    """Run DeepEval quality metrics; return mean scores per metric."""
    cases = test_cases[:max_cases]
    print(f"Running quality tests on {len(cases)} cases...")
    llm_cases: list[LLMTestCase] = []
    for i, tc in enumerate(cases, 1):
        query_preview = tc["input"][:50] + "..." if len(tc["input"]) > 50 else tc["input"]
        print(f"  [{i}/{len(cases)}] {query_preview}", end="\r")
        data = query_api(client, tc["input"])
        retrieval_context = [s["excerpt"] for s in data.get("sources", [])]
        answer_text = data.get("answer") or data.get("reason") or ""
        llm_cases.append(
            LLMTestCase(
                input=tc["input"],
                actual_output=answer_text,
                expected_output=tc.get("expected_output"),
                retrieval_context=retrieval_context,
            )
        )
    print()  # Clear progress line

    metric_classes = [
        (FaithfulnessMetric, "faithfulness"),
        (AnswerRelevancyMetric, "answer_relevancy"),
        (ContextualPrecisionMetric, "contextual_precision"),
        (ContextualRecallMetric, "contextual_recall"),
    ]
    scores: dict[str, list[float]] = {name: [] for _, name in metric_classes}
    for metric_cls, name in metric_classes:
        print(f"Evaluating {name}...")
        for tc in llm_cases:
            m = metric_cls(threshold=0.7)
            m.measure(tc)
            if hasattr(m, "score") and m.score is not None:
                scores[name].append(float(m.score))
    return {k: sum(v) / len(v) if v else 0.0 for k, v in scores.items()}


def run_performance(client: httpx.Client, test_cases: list[dict], n: int = 20) -> dict[str, float]:
    """Run query latency; return p50/p95/p99 in ms."""
    cases = test_cases[:n] if len(test_cases) >= n else test_cases
    print(f"Running performance tests on {len(cases)} cases...")
    latencies = []
    for i, tc in enumerate(cases, 1):
        print(f"  [{i}/{len(cases)}] Measuring latency...", end="\r")
        start = time.perf_counter()
        r = client.post("/query", json={"query": tc["input"]})
        r.raise_for_status()
        latencies.append((time.perf_counter() - start) * 1000)
    print()  # Clear progress line
    latencies.sort()
    if not latencies:
        return {"p50_ms": 0, "p95_ms": 0, "p99_ms": 0}

    def pct(p: float) -> float:
        k = (len(latencies) - 1) * (p / 100)
        f = int(k)
        c = min(f + 1, len(latencies) - 1)
        return latencies[f] + (k - f) * (latencies[c] - latencies[f])

    return {"p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99)}


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG efficiency testing CLI")
    parser.add_argument("--api-url", default="http://localhost:8000", help="RAG API base URL")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("efficiency_results.json"),
        help="JSON output path",
    )
    parser.add_argument(
        "--test-types",
        choices=["all", "quality", "performance"],
        default="all",
    )
    parser.add_argument(
        "--pov",
        type=Path,
        default=None,
        help="PoV report path (markdown)",
    )
    parser.add_argument(
        "--max-quality-cases",
        type=int,
        default=15,
        help="Max cases for quality run",
    )
    args = parser.parse_args()

    test_cases = load_test_cases()
    quality: dict[str, float] = {}
    performance: dict[str, float] = {}

    try:
        with httpx.Client(base_url=args.api_url, timeout=60.0) as client:
            if args.test_types in ("all", "quality"):
                quality = run_quality(client, test_cases, max_cases=args.max_quality_cases)
            if args.test_types in ("all", "performance"):
                performance = run_performance(client, test_cases)
    except (httpx.ConnectError, httpx.HTTPStatusError) as e:
        print(f"API error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Test execution failed: {e}", file=sys.stderr)
        if args.test_types == "quality":
            return 1

    report = build_report(quality, performance)
    write_json(report, args.output)
    print(f"Wrote {args.output}")

    if args.pov is not None:
        args.pov.write_text(render_pov(report), encoding="utf-8")
        print(f"Wrote PoV report {args.pov}")

    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
