from __future__ import annotations

import json

from rag_api.services.metrics import emf_logger
from rag_api.services.metrics import CloudWatchMetrics


def test_record_source_attribution_complete_emits_expected_metrics(monkeypatch):
    captured = {}

    def fake_emit(self, metrics, dimensions=None):
        captured["metrics"] = metrics
        captured["dimensions"] = dimensions

    monkeypatch.setattr(CloudWatchMetrics, "_emit_emf", fake_emit)

    cw = CloudWatchMetrics(enabled=True)
    cw.record_source_attribution(complete=True, endpoint="/query")

    assert captured["metrics"]["SourceAttributionComplete"] == (1, "Count")
    assert captured["metrics"]["SourceAttributionCount"] == (1, "Count")
    assert captured["dimensions"] == {"Endpoint": "/query", "Status": "complete"}


def test_record_source_attribution_missing_emits_expected_metrics(monkeypatch):
    captured = {}

    def fake_emit(self, metrics, dimensions=None):
        captured["metrics"] = metrics
        captured["dimensions"] = dimensions

    monkeypatch.setattr(CloudWatchMetrics, "_emit_emf", fake_emit)

    cw = CloudWatchMetrics(enabled=True)
    cw.record_source_attribution(complete=False, endpoint="/query")

    assert captured["metrics"]["SourceAttributionComplete"] == (0, "Count")
    assert captured["metrics"]["SourceAttributionCount"] == (1, "Count")
    assert captured["dimensions"] == {"Endpoint": "/query", "Status": "missing"}


def test_emit_emf_logs_json_message(monkeypatch):
    captured: dict[str, str] = {}

    def fake_info(message):
        captured["message"] = message

    monkeypatch.setattr(emf_logger, "info", fake_info)

    cw = CloudWatchMetrics(namespace="RAG/Starter", enabled=True)
    cw._emit_emf(
        metrics={"QueryCount": (1, "Count")},
        dimensions={"Status": "success", "Endpoint": "/query"},
    )

    payload = json.loads(captured["message"])
    cw_metrics = payload["_aws"]["CloudWatchMetrics"][0]
    assert payload["QueryCount"] == 1
    assert payload["Status"] == "success"
    assert payload["Endpoint"] == "/query"
    assert cw_metrics["Namespace"] == "RAG/Starter"
    assert cw_metrics["Dimensions"] == [["Status", "Endpoint"]]
    assert cw_metrics["Metrics"] == [{"MetricName": "QueryCount", "Unit": "Count"}]
    assert isinstance(payload["_aws"]["Timestamp"], int)
