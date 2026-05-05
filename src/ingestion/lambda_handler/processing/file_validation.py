"""File content validation for ingestion extraction."""

from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from dataclasses import dataclass

from .extractors import ExtractorRegistry

ZIP_SIGNATURE = b"PK\x03\x04"
OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
PDF_SIGNATURE = b"%PDF-"
STRICTLY_VALIDATED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".xls",
    ".json",
    ".csv",
    ".txt",
    ".md",
    ".html",
    ".htm",
}
TEXT_FAMILY_EXTENSIONS = {".txt", ".md", ".html", ".htm"}
MIME_TYPE_TO_EXTENSION = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/html": ".html",
    "text/csv": ".csv",
    "application/json": ".json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
}


@dataclass(frozen=True)
class ValidationFailure(Exception):
    """Raised when content does not match the expected format."""

    reason: str
    expected: str
    detected: str

    def __str__(self) -> str:
        return (
            f"{self.reason}: expected={self.expected or 'unknown'} "
            f"detected={self.detected or 'unknown'}"
        )


def resolve_validated_extension(
    *,
    key: str,
    content_type: str,
    data: bytes,
    extractor_registry: ExtractorRegistry,
) -> str:
    """Resolve extension and validate that bytes match supported format."""
    key_ext = os.path.splitext(key.lower())[1]
    key_ext = key_ext if extractor_registry.get(key_ext) else ""

    mime_ext = _mime_to_extension(content_type)
    mime_ext = mime_ext if extractor_registry.get(mime_ext) else ""

    signature_ext = detect_content_extension(data)
    supported_signature_ext = signature_ext if extractor_registry.get(signature_ext) else ""

    # Prefer explicit file extension when supported, but enforce signature compatibility.
    if key_ext:
        if key_ext in STRICTLY_VALIDATED_EXTENSIONS:
            if signature_ext and not _is_compatible_signature(
                expected=key_ext, detected=signature_ext
            ):
                raise ValidationFailure(
                    reason="file signature mismatch",
                    expected=key_ext,
                    detected=signature_ext,
                )
            _validate_for_extension(ext=key_ext, data=data)
        return key_ext

    # No trusted extension on filename; use signature first, MIME fallback second.
    if supported_signature_ext:
        _validate_for_extension(ext=supported_signature_ext, data=data)
        return supported_signature_ext

    if mime_ext:
        _validate_for_extension(ext=mime_ext, data=data)
        return mime_ext

    return ""


def detect_content_extension(data: bytes) -> str:
    """Detect best-effort extension by file signatures and parse checks."""
    if data.startswith(PDF_SIGNATURE):
        return ".pdf"

    if data.startswith(OLE_SIGNATURE):
        return ".xls"

    if data.startswith(ZIP_SIGNATURE):
        office_ext = _detect_office_zip_extension(data)
        if office_ext:
            return office_ext

    if _looks_like_json(data):
        return ".json"

    if _looks_like_csv(data):
        return ".csv"

    if _is_text_payload(data):
        return ".txt"

    return ""


def _mime_to_extension(content_type: str) -> str:
    normalized = content_type.split(";", maxsplit=1)[0].strip().lower()
    return MIME_TYPE_TO_EXTENSION.get(normalized, "")


def _detect_office_zip_extension(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = {name.lower() for name in zf.namelist()}
    except zipfile.BadZipFile:
        return ""

    if any(name.startswith("word/") for name in names):
        return ".docx"
    if any(name.startswith("xl/") for name in names):
        return ".xlsx"
    return ""


def _validate_for_extension(*, ext: str, data: bytes) -> None:
    if ext == ".pdf" and not data.startswith(PDF_SIGNATURE):
        raise ValidationFailure(
            "invalid pdf signature", expected=ext, detected=detect_content_extension(data)
        )
    if ext == ".docx" and _detect_office_zip_extension(data) != ".docx":
        raise ValidationFailure(
            "invalid docx signature", expected=ext, detected=detect_content_extension(data)
        )
    if ext == ".xlsx" and _detect_office_zip_extension(data) != ".xlsx":
        raise ValidationFailure(
            "invalid xlsx signature", expected=ext, detected=detect_content_extension(data)
        )
    if ext == ".xls" and not data.startswith(OLE_SIGNATURE):
        raise ValidationFailure(
            "invalid xls signature", expected=ext, detected=detect_content_extension(data)
        )
    if ext == ".json" and not _looks_like_json(data):
        raise ValidationFailure(
            "invalid json payload", expected=ext, detected=detect_content_extension(data)
        )
    if ext == ".csv" and not _looks_like_csv(data):
        raise ValidationFailure(
            "invalid csv payload", expected=ext, detected=detect_content_extension(data)
        )
    if ext in {".txt", ".md", ".html", ".htm"} and not _is_text_payload(data):
        raise ValidationFailure(
            "invalid text payload", expected=ext, detected=detect_content_extension(data)
        )


def _looks_like_json(data: bytes) -> bool:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False

    stripped = text.strip()
    if not stripped:
        return False
    if stripped[0] not in "{[":
        return False

    try:
        json.loads(stripped)
        return True
    except json.JSONDecodeError:
        return False


def _looks_like_csv(data: bytes) -> bool:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False

    sample = "\n".join(lines[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return False

    return dialect.delimiter in sample


def _is_text_payload(data: bytes) -> bool:
    if not data:
        return True

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False

    disallowed = 0
    for ch in text:
        if ch in "\n\r\t":
            continue
        if ord(ch) < 32:
            disallowed += 1

    return (disallowed / max(len(text), 1)) < 0.02


def _is_compatible_signature(*, expected: str, detected: str) -> bool:
    if expected == detected:
        return True

    # Markdown and HTML are plain text containers, so signature-level detection
    # often classifies them as generic text.
    if expected in TEXT_FAMILY_EXTENSIONS and detected in TEXT_FAMILY_EXTENSIONS:
        return True

    return False
