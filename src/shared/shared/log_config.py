"""Structured JSON logging configuration with correlation ID injection."""

import json
import logging
from datetime import datetime, timezone

from .correlation import get_correlation_id


class CorrelationIDFilter(logging.Filter):
    """Logging filter that injects correlation ID into all log records."""

    def __init__(self, service: str = "unknown"):
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id and service to log record.

        Args:
            record: Log record to enhance

        Returns:
            True to allow the record to be logged
        """
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id if correlation_id else None
        record.service = self.service
        return True


class JSONFormatter(logging.Formatter):
    """JSON formatter that outputs structured logs."""

    def __init__(self, service: str = "unknown"):
        super().__init__()
        self.service = service

    @staticmethod
    def _is_emf_payload(message: str) -> bool:
        """Return True when message is a valid EMF JSON document."""
        if not message or not message.startswith("{"):
            return False
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            return False
        aws_meta = payload.get("_aws")
        if not isinstance(aws_meta, dict):
            return False
        return isinstance(aws_meta.get("CloudWatchMetrics"), list)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        message = record.getMessage()

        # Emit raw EMF line to allow CloudWatch extraction.
        if record.name == "rag_api.emf" and self._is_emf_payload(message):
            return message

        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": message,
            "service": getattr(record, "service", self.service),
            "logger": record.name,
        }

        # Add correlation ID if present
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_obj["correlation_id"] = record.correlation_id

        # Add component if present
        if hasattr(record, "component"):
            log_obj["component"] = record.component

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(
    service: str = "unknown",
    use_json: bool = True,
    level: int = logging.INFO,
) -> None:
    """Configure logging with correlation ID support.

    Args:
        service: Service name for log identification
        use_json: Whether to use JSON formatting (vs. standard formatting)
        level: Logging level (default INFO)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # Add correlation ID filter
    handler.addFilter(CorrelationIDFilter(service=service))

    # Set formatter
    if use_json:
        formatter = JSONFormatter(service=service)
    else:
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s"
        formatter = logging.Formatter(fmt)

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
