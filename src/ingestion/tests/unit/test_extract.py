"""Unit tests for extraction orchestration."""

from __future__ import annotations

import io

from lambda_handler.processing.extract import extract_text_from_s3_object
from lambda_handler.processing.extractors import ExtractorRegistry


class _StubExtractor:
    def __init__(self, output: str):
        self.output = output
        self.calls: list[tuple[bytes, str]] = []

    def extract(self, data: bytes, key: str) -> str:
        self.calls.append((data, key))
        return self.output


def _mock_s3_response(data: bytes, content_type: str) -> dict:
    return {
        "Body": io.BytesIO(data),
        "ContentType": content_type,
    }


def test_extract_uses_mime_fallback_when_extension_missing():
    registry = ExtractorRegistry()
    csv_extractor = _StubExtractor("csv-output")
    registry.register(".csv", csv_extractor)

    class MockS3:
        def get_object(self, Bucket: str, Key: str) -> dict:
            assert Bucket == "bucket"
            assert Key == "uploads/datafile"
            return _mock_s3_response(b"a,b\n1,2", "text/csv")

    text = extract_text_from_s3_object(
        bucket="bucket",
        key="uploads/datafile",
        s3_client=MockS3(),
        extractor_registry=registry,
    )

    assert text == "csv-output"
    assert len(csv_extractor.calls) == 1


def test_extract_prefers_supported_extension_over_mime():
    registry = ExtractorRegistry()
    txt_extractor = _StubExtractor("txt-output")
    json_extractor = _StubExtractor("json-output")
    registry.register(".txt", txt_extractor)
    registry.register(".json", json_extractor)

    class MockS3:
        def get_object(self, Bucket: str, Key: str) -> dict:
            return _mock_s3_response(b"hello", "application/json")

    text = extract_text_from_s3_object(
        bucket="bucket",
        key="uploads/readme.txt",
        s3_client=MockS3(),
        extractor_registry=registry,
    )

    assert text == "txt-output"
    assert len(txt_extractor.calls) == 1
    assert len(json_extractor.calls) == 0


def test_extract_uses_mime_when_extension_unsupported():
    registry = ExtractorRegistry()
    json_extractor = _StubExtractor("json-output")
    registry.register(".json", json_extractor)

    class MockS3:
        def get_object(self, Bucket: str, Key: str) -> dict:
            return _mock_s3_response(b'{"ok": true}', "application/json; charset=utf-8")

    text = extract_text_from_s3_object(
        bucket="bucket",
        key="uploads/payload.bin",
        s3_client=MockS3(),
        extractor_registry=registry,
    )

    assert text == "json-output"
    assert len(json_extractor.calls) == 1


def test_extract_rejects_mismatched_signature_and_extension():
    registry = ExtractorRegistry()
    pdf_extractor = _StubExtractor("pdf-output")
    registry.register(".pdf", pdf_extractor)

    class MockS3:
        def get_object(self, Bucket: str, Key: str) -> dict:
            return _mock_s3_response(b'{"not":"pdf"}', "application/json")

    text = extract_text_from_s3_object(
        bucket="bucket",
        key="uploads/report.pdf",
        s3_client=MockS3(),
        extractor_registry=registry,
    )

    assert text == ""
    assert len(pdf_extractor.calls) == 0


def test_extract_rejects_invalid_json_payload():
    registry = ExtractorRegistry()
    json_extractor = _StubExtractor("json-output")
    registry.register(".json", json_extractor)

    class MockS3:
        def get_object(self, Bucket: str, Key: str) -> dict:
            return _mock_s3_response(b"just some text", "application/json")

    text = extract_text_from_s3_object(
        bucket="bucket",
        key="uploads/config.json",
        s3_client=MockS3(),
        extractor_registry=registry,
    )

    assert text == ""
    assert len(json_extractor.calls) == 0
