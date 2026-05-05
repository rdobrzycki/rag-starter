"""Unit tests for file content validation."""

from __future__ import annotations

import io
import zipfile

import pytest

from lambda_handler.processing.extractors import default_extractor_registry
from lambda_handler.processing.file_validation import (
    ValidationFailure,
    detect_content_extension,
    resolve_validated_extension,
)


def _office_zip(*names: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in names:
            zf.writestr(name, "placeholder")
    return buf.getvalue()


def test_detect_content_extension_pdf():
    assert detect_content_extension(b"%PDF-1.7\n%...\n") == ".pdf"


def test_resolve_extension_uses_signature_when_missing_extension():
    ext = resolve_validated_extension(
        key="uploads/document",
        content_type="application/json",
        data=b'{"status": "ok"}',
        extractor_registry=default_extractor_registry(),
    )
    assert ext == ".json"


def test_resolve_extension_rejects_signature_mismatch():
    with pytest.raises(ValidationFailure, match="file signature mismatch"):
        resolve_validated_extension(
            key="uploads/report.pdf",
            content_type="application/pdf",
            data=b"not a real pdf payload",
            extractor_registry=default_extractor_registry(),
        )


def test_resolve_extension_rejects_invalid_json():
    with pytest.raises(ValidationFailure, match="file signature mismatch"):
        resolve_validated_extension(
            key="uploads/config.json",
            content_type="application/json",
            data=b"plain text payload",
            extractor_registry=default_extractor_registry(),
        )


def test_resolve_extension_detects_docx_signature():
    ext = resolve_validated_extension(
        key="uploads/file.bin",
        content_type="application/octet-stream",
        data=_office_zip("word/document.xml", "[Content_Types].xml"),
        extractor_registry=default_extractor_registry(),
    )
    assert ext == ".docx"


def test_resolve_extension_allows_text_family_signature_compatibility():
    ext = resolve_validated_extension(
        key="uploads/readme.md",
        content_type="text/markdown",
        data=b"# Heading\nSome markdown content.\n",
        extractor_registry=default_extractor_registry(),
    )
    assert ext == ".md"
