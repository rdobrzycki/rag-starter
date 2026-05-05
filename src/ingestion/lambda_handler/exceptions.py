"""Exception classes for document ingestion."""


class IngestionError(Exception):
    """Base exception for ingestion errors."""


class ConfigurationError(IngestionError):
    """Configuration retrieval failed."""


class ProcessingError(IngestionError):
    """Text processing or embedding failed."""


class VectorStorageError(IngestionError):
    """Vector storage failed."""


class FileTooLargeError(IngestionError):
    """File exceeds size limit (rejection)."""


class NoExtractableTextError(IngestionError):
    """No text could be extracted from file (rejection)."""


class TextTooLargeError(IngestionError):
    """Extracted text exceeds character limit (rejection)."""
