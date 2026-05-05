from __future__ import annotations

import json
import logging

from shared.log_config import JSONFormatter


def test_json_formatter_passes_through_emf_records() -> None:
    formatter = JSONFormatter(service="rag-api")
    emf_message = (
        '{"_aws":{"Timestamp":1,"CloudWatchMetrics":[{"Namespace":"RAG/Starter","Metrics":[],'
        '"Dimensions":[[]]}]},"QueryCount":1}'
    )
    record = logging.LogRecord(
        name="rag_api.emf",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=emf_message,
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)
    assert rendered == emf_message


def test_json_formatter_wraps_non_emf_records() -> None:
    formatter = JSONFormatter(service="rag-api")
    record = logging.LogRecord(
        name="rag_api.services.metrics",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="CloudWatch metric",
        args=(),
        exc_info=None,
    )

    rendered = formatter.format(record)
    payload = json.loads(rendered)
    assert payload["message"] == "CloudWatch metric"
    assert payload["logger"] == "rag_api.services.metrics"
