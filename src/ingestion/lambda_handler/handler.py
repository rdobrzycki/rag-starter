"""Lambda handler for S3-triggered document ingestion.

This module processes documents uploaded to S3 by extracting text,
chunking it, generating embeddings, and storing vectors in Qdrant.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from awslambdaric.lambda_context import LambdaContext
else:
    LambdaContext = Any

from .exceptions import (
    ConfigurationError,
    FileTooLargeError,
    NoExtractableTextError,
    ProcessingError,
    TextTooLargeError,
    VectorStorageError,
)
from .models import IngestionStatus, RejectionReason
from .core.orchestration import (
    build_error_response,
    initialize_clients_and_config,
    process_document,
    setup_ingestion_context,
)

# Configure logging level from environment variable (before any loggers are created)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level_value = getattr(logging, LOG_LEVEL, logging.INFO)

# Configure root logger
logging.basicConfig(
    level=log_level_value,
    force=True,  # Force reconfiguration even if already configured
    format="[%(levelname)s] %(name)s: %(message)s",
)

# Set level on root logger explicitly
logging.getLogger().setLevel(log_level_value)

logger = logging.getLogger(__name__)


def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler for S3-triggered document ingestion.

    Processes documents uploaded to S3 by extracting text, chunking,
    generating embeddings, and storing vectors in Qdrant.

    Args:
        event: Lambda event with S3 notification
        context: Lambda context object

    Returns:
        Status dictionary with processing results
    """
    # Ensure all module loggers use INFO level
    for logger_name in [
        "lambda_handler",
        "lambda_handler.config",
        "lambda_handler.clients",
        "shared",
    ]:
        logging.getLogger(logger_name).setLevel(log_level_value)

    correlation_id: str | None = None
    try:
        logger.info("100. Starting ingestion", extra={"event": event, "context": context})
        region = os.environ.get("AWS_REGION")
        # Load config first so we fail fast on missing/invalid config
        logger.info("110. Initializing clients and config", extra={"region": region})
        s3, ssm, secrets, config = initialize_clients_and_config(region)
        logger.info(
            "120. Clients and config initialized",
            extra={"s3": s3, "ssm": ssm, "secrets": secrets, "config": config},
        )
        correlation_id, bucket, key = setup_ingestion_context(event, context)
        logger.info(
            "130. Setup ingestion context",
            extra={"correlation_id": correlation_id, "bucket": bucket, "key": key},
        )
        # Process document
        result = process_document(
            bucket=bucket,
            key=key,
            s3_client=s3,
            config=config,
            region=region,
            correlation_id=correlation_id,
            aws_request_id=context.aws_request_id,
        )
        logger.info("140. Document processed", extra={"result": result})
        return {
            "status": IngestionStatus.OK.value,
            **result,
        }

    except FileTooLargeError as e:
        return build_error_response(
            e,
            correlation_id,
            IngestionStatus.REJECTED,
            RejectionReason.FILE_TOO_LARGE,
        )
    except NoExtractableTextError as e:
        return build_error_response(
            e,
            correlation_id,
            IngestionStatus.REJECTED,
            RejectionReason.NO_EXTRACTABLE_TEXT,
        )
    except TextTooLargeError as e:
        return build_error_response(
            e,
            correlation_id,
            IngestionStatus.REJECTED,
            RejectionReason.TEXT_TOO_LARGE,
        )
    except (ConfigurationError, ProcessingError, VectorStorageError) as e:
        return build_error_response(e, correlation_id, IngestionStatus.ERROR)
    except Exception as e:
        logger.exception(
            "Unexpected error during ingestion",
            extra={
                "correlation_id": correlation_id,
                "error_type": type(e).__name__,
            },
        )
        return {
            "status": IngestionStatus.ERROR.value,
            "error": f"Unexpected error: {e}",
        }
