from __future__ import annotations
import json
import time
import logging
import boto3
from botocore.exceptions import ClientError, ConnectionError
from typing import TYPE_CHECKING

from shared.bedrock_utils import is_retryable_bedrock_error
from shared.correlation import get_correlation_id
from shared.retry import retry_with_backoff

if TYPE_CHECKING:
    from .services.metrics import CloudWatchMetrics

logger = logging.getLogger(__name__)


class Bedrock:
    def __init__(self, region: str, metrics: "CloudWatchMetrics | None" = None):
        self._runtime = boto3.client("bedrock-runtime", region_name=region)
        self._metrics = metrics

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(ConnectionError, ClientError),
        should_retry=is_retryable_bedrock_error,
        operation_name="bedrock_embed",
    )
    def embed(self, model_id: str, text: str) -> list[float]:
        start_time = time.time()
        correlation_id = get_correlation_id()
        try:
            resp = self._runtime.invoke_model(
                modelId=model_id, body=json.dumps({"inputText": text})
            )
            data = json.loads(resp["body"].read())
            latency_ms = (time.time() - start_time) * 1000

            logger.debug(
                "Bedrock embed request completed",
                extra={
                    "correlation_id": correlation_id,
                    "model_id": model_id,
                    "latency_ms": latency_ms,
                },
            )

            if self._metrics:
                self._metrics.record_bedrock_call(
                    latency_ms=latency_ms,
                    success=True,
                    operation="embed",
                    model_id=model_id,
                )

            return data["embedding"]
        except (ConnectionError, ClientError) as e:
            latency_ms = (time.time() - start_time) * 1000

            logger.warning(
                "Bedrock embed request failed",
                extra={
                    "correlation_id": correlation_id,
                    "model_id": model_id,
                    "error": str(e),
                },
            )

            if self._metrics:
                self._metrics.record_bedrock_call(
                    latency_ms=latency_ms,
                    success=False,
                    operation="embed",
                    model_id=model_id,
                )

            if not is_retryable_bedrock_error(e):
                logger.debug("Non-retryable Bedrock error: %s", str(e))
            raise

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(ConnectionError, ClientError),
        should_retry=is_retryable_bedrock_error,
        operation_name="bedrock_invoke",
    )
    def invoke(self, model_id: str, payload: dict) -> dict:
        start_time = time.time()
        correlation_id = get_correlation_id()
        try:
            resp = self._runtime.invoke_model(modelId=model_id, body=json.dumps(payload))
            result = json.loads(resp["body"].read())
            latency_ms = (time.time() - start_time) * 1000

            logger.debug(
                "Bedrock invoke request completed",
                extra={
                    "correlation_id": correlation_id,
                    "model_id": model_id,
                    "latency_ms": latency_ms,
                },
            )

            if self._metrics:
                self._metrics.record_bedrock_call(
                    latency_ms=latency_ms,
                    success=True,
                    operation="invoke",
                    model_id=model_id,
                )

            return result
        except (ConnectionError, ClientError) as e:
            latency_ms = (time.time() - start_time) * 1000

            logger.warning(
                "Bedrock invoke request failed",
                extra={
                    "correlation_id": correlation_id,
                    "model_id": model_id,
                    "error": str(e),
                },
            )

            if self._metrics:
                self._metrics.record_bedrock_call(
                    latency_ms=latency_ms,
                    success=False,
                    operation="invoke",
                    model_id=model_id,
                )

            if not is_retryable_bedrock_error(e):
                logger.debug("Non-retryable Bedrock error: %s", str(e))
            raise
