"""JSON and PoV report generation for RAG efficiency runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_report(
    quality: dict[str, float],
    performance: dict[str, float],
    *,
    passed: bool | None = None,
) -> dict[str, Any]:
    """Build report dict for JSON output."""
    score = (sum(quality.values()) / len(quality)) if quality else 0.0
    if passed is None:
        passed = score >= 0.7 and performance.get("p95_ms", 99999) < 5000
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "quality": quality,
        "performance": performance,
        "summary": {"passed": passed, "score": round(score, 4)},
    }


def write_json(report: dict[str, Any], path: Path) -> None:
    """Write report as JSON to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(report, f, indent=2)


def render_pov(report: dict[str, Any]) -> str:
    """Render Proof-of-Value report (markdown). TBYB client-facing names."""
    q = report.get("quality", {})
    p = report.get("performance", {})
    s = report.get("summary", {})
    gar = q.get("faithfulness", 0)
    lines = [
        "# RAG Proof-of-Value Report",
        "",
        f"**Generated:** {report.get('timestamp', '')}",
        f"**Result:** {'PASS' if s.get('passed') else 'FAIL'} (score {s.get('score', 0):.2f})",
        "",
        "## Executive Summary",
        "",
        "This report summarizes RAG quality and performance metrics.",
        "",
        "## Answer Quality Metrics",
        "",
        "| Metric | Value | TBYB Name |",
        "|--------|-------|-----------|",
        f"| Faithfulness | {gar:.2f} | GAR (Grounded Answer Rate) |",
        f"| Answer Relevancy | {q.get('answer_relevancy', 0):.2f} | Accuracy |",
        f"| Context Precision | {q.get('contextual_precision', 0):.2f} | Precision |",
        f"| Context Recall | {q.get('contextual_recall', 0):.2f} | CCS |",
        f"| Hallucination Rate | {1 - gar:.2f} | HR (1 - GAR) |",
        "",
        "## Performance",
        "",
        f"- P50: {p.get('p50_ms', 0):.0f} ms",
        f"- P95: {p.get('p95_ms', 0):.0f} ms",
        f"- P99: {p.get('p99_ms', 0):.0f} ms",
        "",
        "## Known Limitations",
        "",
        "Metrics depend on test corpus and API. Run against deployed API for production.",
        "",
    ]
    return "\n".join(lines)
