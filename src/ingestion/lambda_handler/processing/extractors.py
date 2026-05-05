"""Text extraction registry for document ingestion.

Provides extensible extraction framework using strategy pattern.
Customers can register custom extractors for new file formats (CSV, JSON, Excel)
without modifying core extraction code.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Protocol

import pandas as pd
from docx import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class TextExtractor(Protocol):
    """Protocol for text extractors.

    Extractors convert file bytes to plain text for a specific format.
    """

    def extract(self, data: bytes, key: str) -> str:
        """Extract text from file bytes.

        Args:
            data: File content as bytes
            key: S3 object key (for logging/context)

        Returns:
            Extracted text content

        Raises:
            Exception: If extraction fails
        """
        ...


class PdfExtractor:
    """Extracts text from PDF files."""

    def extract(self, data: bytes, key: str) -> str:
        """Extract text from PDF bytes.

        Args:
            data: PDF file bytes
            key: S3 object key (for logging)

        Returns:
            Extracted text content
        """
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()


class DocxExtractor:
    """Extracts text from DOCX files."""

    def extract(self, data: bytes, key: str) -> str:
        """Extract text from DOCX bytes.

        Args:
            data: DOCX file bytes
            key: S3 object key (for logging)

        Returns:
            Extracted text content
        """
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()


class PlainTextExtractor:
    """Extracts text from plain text files (TXT, MD, HTML, HTM)."""

    def extract(self, data: bytes, key: str) -> str:
        """Decode plain text from bytes.

        Args:
            data: Text file bytes
            key: S3 object key (for logging)

        Returns:
            Decoded text content
        """
        return data.decode("utf-8", errors="ignore")


class CsvExtractor:
    """Extracts text from CSV files with auto-delimiter detection.

    Converts CSV data to RAG-optimized format with column=value pairs.
    Example output:
        Row 1: Product=Widget, Price=10, Stock=5
        Row 2: Product=Gadget, Price=20, Stock=3
    """

    def extract(self, data: bytes, key: str) -> str:
        """Extract text from CSV bytes.

        Args:
            data: CSV file bytes
            key: S3 object key (for logging)

        Returns:
            Extracted text with labeled row format
        """
        try:
            df = pd.read_csv(
                io.BytesIO(data),
                sep=None,  # Auto-detect delimiter
                engine="python",
                on_bad_lines="skip",  # Skip malformed lines
            )

            if df.empty:
                return ""

            lines = []
            for idx, row in df.iterrows():
                # Convert row to column=value pairs
                pairs = [f"{col}={row[col]}" for col in df.columns]
                lines.append(f"Row {idx + 1}: {', '.join(pairs)}")

            return "\n".join(lines)

        except Exception as e:
            logger.warning("Failed to parse CSV from %s: %s", key, e)
            return ""


class JsonExtractor:
    """Extracts text from JSON files with nested structure flattening.

    Converts JSON to RAG-optimized format with dot notation for nesting.
    Example output:
        user.name: John Doe
        user.email: john@example.com
        items[0].name: Widget
        items[0].price: 10.99
    """

    def extract(self, data: bytes, key: str) -> str:
        """Extract text from JSON bytes.

        Args:
            data: JSON file bytes
            key: S3 object key (for logging)

        Returns:
            Extracted text with flattened key-value pairs
        """
        try:
            obj = json.loads(data.decode("utf-8", errors="ignore"))
            lines = self._flatten_json(obj)
            return "\n".join(lines)

        except Exception as e:
            logger.warning("Failed to parse JSON from %s: %s", key, e)
            return ""

    def _flatten_json(self, obj: Any, prefix: str = "") -> list[str]:
        """Recursively flatten JSON structure.

        Args:
            obj: JSON object (dict, list, or primitive)
            prefix: Current key path prefix

        Returns:
            List of flattened key: value strings
        """
        lines = []

        if isinstance(obj, dict):
            for key, value in obj.items():
                new_prefix = f"{prefix}.{key}" if prefix else key
                lines.extend(self._flatten_json(value, new_prefix))

        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                new_prefix = f"{prefix}[{idx}]"
                lines.extend(self._flatten_json(item, new_prefix))

        else:
            # Primitive value
            lines.append(f"{prefix}: {obj}")

        return lines


class ExcelExtractor:
    """Extracts text from Excel files (.xlsx, .xls) with multi-sheet support.

    Converts Excel data to RAG-optimized format with sheet headers and column=value pairs.
    Example output:
        === Sheet: Products ===
        Row 1: Product=Widget, Price=10, Stock=5
        Row 2: Product=Gadget, Price=20, Stock=3

        === Sheet: Orders ===
        Row 1: OrderID=001, Customer=Alice, Total=30
    """

    def extract(self, data: bytes, key: str) -> str:
        """Extract text from Excel bytes.

        Args:
            data: Excel file bytes
            key: S3 object key (for logging)

        Returns:
            Extracted text with all sheets in labeled format
        """
        try:
            extension = key.rsplit(".", maxsplit=1)[-1].lower() if "." in key else ""
            engine = "xlrd" if extension == "xls" else "openpyxl"

            # Read all sheets
            sheets = pd.read_excel(
                io.BytesIO(data),
                sheet_name=None,  # Read all sheets
                engine=engine,
            )

            if not sheets:
                return ""

            sheet_texts = []

            for sheet_name, df in sheets.items():
                if df.empty:
                    continue

                lines = [f"=== Sheet: {sheet_name} ==="]

                for idx, row in df.iterrows():
                    # Convert row to column=value pairs
                    pairs = [f"{col}={row[col]}" for col in df.columns]
                    lines.append(f"Row {idx + 1}: {', '.join(pairs)}")

                sheet_texts.append("\n".join(lines))

            return "\n\n".join(sheet_texts)

        except Exception as e:
            logger.warning("Failed to parse Excel from %s: %s", key, e)
            return ""


class ExtractorRegistry:
    """Registry of text extractors keyed by file extension."""

    def __init__(self):
        """Initialize empty registry."""
        self._extractors: dict[str, TextExtractor] = {}

    def register(self, extension: str, extractor: TextExtractor) -> None:
        """Register an extractor for a file extension.

        Args:
            extension: File extension with leading dot (e.g. '.pdf')
            extractor: TextExtractor instance
        """
        self._extractors[extension.lower()] = extractor
        logger.debug("Registered extractor for %s", extension)

    def get(self, extension: str) -> TextExtractor | None:
        """Get extractor for file extension.

        Args:
            extension: File extension with leading dot (e.g. '.pdf')

        Returns:
            TextExtractor instance or None if not registered
        """
        return self._extractors.get(extension.lower())

    def extensions(self) -> list[str]:
        """Get list of registered extensions.

        Returns:
            List of file extensions (e.g. ['.pdf', '.docx', '.txt'])
        """
        return list(self._extractors.keys())


def default_extractor_registry() -> ExtractorRegistry:
    """Create default extractor registry with built-in extractors.

    Returns:
        Registry with PDF, DOCX, plain text, CSV, JSON, and Excel extractors
    """
    registry = ExtractorRegistry()

    # PDF extractor
    registry.register(".pdf", PdfExtractor())

    # DOCX extractor
    registry.register(".docx", DocxExtractor())

    # Plain text extractors (same extractor for multiple extensions)
    plain_text = PlainTextExtractor()
    for ext in [".txt", ".md", ".html", ".htm"]:
        registry.register(ext, plain_text)

    # CSV extractor
    registry.register(".csv", CsvExtractor())

    # JSON extractor
    registry.register(".json", JsonExtractor())

    # Excel extractors (same extractor for both formats)
    excel = ExcelExtractor()
    for ext in [".xlsx", ".xls"]:
        registry.register(ext, excel)

    return registry
