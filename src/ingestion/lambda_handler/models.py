"""Data models, types, and constants for document ingestion."""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


# Constants organization
class Limits:
    """Processing limits for document ingestion."""

    MAX_FILE_MB = 50
    MAX_CHARS = 500_000
    MAX_CHUNKS = 500
    BYTES_PER_MB = 1024 * 1024


# Status enums
class IngestionStatus(str, Enum):
    """Status values for ingestion responses."""

    OK = "ok"
    REJECTED = "rejected"
    ERROR = "error"


class RejectionReason(str, Enum):
    """Rejection reason values."""

    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"
    TEXT_TOO_LARGE = "TEXT_TOO_LARGE"


class IngestionConfig(TypedDict):
    """Configuration for document ingestion."""

    qdrant_url: str
    qdrant_api_key: str
    collection: str
    embed_model_id: str
