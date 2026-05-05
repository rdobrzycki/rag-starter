from __future__ import annotations
import json
import logging
import boto3
from botocore.exceptions import ClientError, ConnectionError

from shared.bedrock_utils import is_retryable_bedrock_error
from shared.correlation import get_correlation_id
from shared.retry import retry_with_backoff

logger = logging.getLogger(__name__)


class Bedrock:
    def __init__(self, region: str):
        self._runtime = boto3.client("bedrock-runtime", region_name=region)

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(ConnectionError, ClientError),
        operation_name="bedrock_embed",
    )
    def embed(self, model_id: str, text: str) -> list[float]:
        correlation_id = get_correlation_id()
        try:
            resp = self._runtime.invoke_model(
                modelId=model_id, body=json.dumps({"inputText": text})
            )
            data = json.loads(resp["body"].read())

            logger.debug(
                "Bedrock embed request completed",
                extra={
                    "correlation_id": correlation_id,
                    "model_id": model_id,
                },
            )
            return data["embedding"]
        except (ConnectionError, ClientError) as e:
            logger.warning(
                "Bedrock embed request failed",
                extra={
                    "correlation_id": correlation_id,
                    "model_id": model_id,
                    "error": str(e),
                },
            )
            if not is_retryable_bedrock_error(e):
                logger.debug("Non-retryable Bedrock error: %s", str(e))
            raise
