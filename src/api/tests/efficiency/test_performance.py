"""RAG performance tests: latency and throughput."""

from __future__ import annotations

import statistics
import time

import pytest


def _query_api(client, query: str) -> float:
    """POST /query; return latency in milliseconds."""
    start = time.perf_counter()
    r = client.post("/query", json={"query": query})
    r.raise_for_status()
    return (time.perf_counter() - start) * 1000


def _percentile(values: list[float], p: float) -> float:
    """Return p-th percentile (0-100) using statistics.quantiles."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    quantiles = statistics.quantiles(values, n=100)
    return quantiles[int(p) - 1]


@pytest.mark.efficiency
def test_query_latency_p95(efficiency_client, test_cases):
    """P95 query latency must be under 5 seconds."""
    cases = test_cases[:20] if len(test_cases) >= 20 else test_cases
    latencies = [_query_api(efficiency_client, tc["input"]) for tc in cases]
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    assert p95 < 5000, f"P95 latency {p95:.0f}ms exceeds 5s (P50={p50:.0f}, P99={p99:.0f})"
