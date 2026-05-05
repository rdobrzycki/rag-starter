from __future__ import annotations

from botocore.exceptions import ClientError

from shared.bedrock_utils import is_retryable_bedrock_error
from shared.id_generation import (
    generate_deterministic_doc_id,
    generate_deterministic_vector_id,
)
from shared.metadata import ChunkMetadata
from shared.qdrant_utils import create_qdrant_client


# ===================================================================
# shared.bedrock_utils
# ===================================================================


def test_bedrock_utils_throttling_is_retryable():
    err = ClientError(
        error_response={"Error": {"Code": "ThrottlingException"}},
        operation_name="InvokeModel",
    )
    assert is_retryable_bedrock_error(err) is True


def test_bedrock_utils_connection_error_is_retryable():
    assert is_retryable_bedrock_error(ConnectionError("reset")) is True


def test_bedrock_utils_access_denied_is_not_retryable():
    err = ClientError(
        error_response={"Error": {"Code": "AccessDeniedException"}},
        operation_name="InvokeModel",
    )
    assert is_retryable_bedrock_error(err) is False


def test_bedrock_utils_unknown_exception_is_not_retryable():
    assert is_retryable_bedrock_error(ValueError("x")) is False


# ===================================================================
# shared.id_generation
# ===================================================================


def test_id_generation_deterministic_same_input():
    doc1 = generate_deterministic_doc_id("s3://bucket/a.txt")
    doc2 = generate_deterministic_doc_id("s3://bucket/a.txt")
    assert doc1 == doc2
    assert len(doc1) == 16

    vec1 = generate_deterministic_vector_id("s3://bucket/a.txt", 0, "abc")
    vec2 = generate_deterministic_vector_id("s3://bucket/a.txt", 0, "abc")
    assert vec1 == vec2
    assert isinstance(vec1, int)


def test_id_generation_different_inputs_produce_different_ids():
    doc_a = generate_deterministic_doc_id("s3://bucket/a.txt")
    doc_b = generate_deterministic_doc_id("s3://bucket/b.txt")
    assert doc_a != doc_b

    vec_a = generate_deterministic_vector_id("s3://bucket/a.txt", 0, "abc")
    vec_b = generate_deterministic_vector_id("s3://bucket/a.txt", 1, "abc")
    assert vec_a != vec_b


def test_vector_id_fits_in_64bit():
    vid = generate_deterministic_vector_id("s3://bucket/x.txt", 9999, "hash")
    assert 0 <= vid < 2**64


# ===================================================================
# shared.metadata
# ===================================================================


def test_metadata_payload_roundtrip_required_fields():
    md = ChunkMetadata(
        doc_id="d1",
        chunk_index=1,
        source_uri="s3://bucket/a.txt",
        text="hello",
        hash="h1",
        created_at="2026-01-01T00:00:00Z",
    )
    payload = md.to_payload()
    out = ChunkMetadata.from_payload(payload)
    assert out.doc_id == "d1"
    assert out.chunk_index == 1
    assert out.doc_name is None


def test_metadata_payload_with_optional_and_additional():
    md = ChunkMetadata(
        doc_id="d2",
        chunk_index=0,
        source_uri="s3://bucket/b.txt",
        text="world",
        hash="h2",
        created_at="2026-01-02T00:00:00Z",
        doc_name="b.txt",
        page_number=3,
        section="intro",
        document_type="pdf",
    )
    payload = md.to_payload({"team": "rag"})
    assert payload["page_number"] == 3
    assert payload["section"] == "intro"
    assert payload["document_type"] == "pdf"
    assert payload["team"] == "rag"

    out = ChunkMetadata.from_payload(payload)
    assert out.page_number == 3
    assert out.doc_name == "b.txt"


def test_metadata_from_payload_uses_defaults_for_missing_keys():
    out = ChunkMetadata.from_payload({})
    assert out.doc_id == ""
    assert out.chunk_index == 0
    assert out.doc_name is None


# ===================================================================
# shared.qdrant_utils  (no key, with key, TypeError fallback)
# ===================================================================


def test_qdrant_utils_with_api_key_skips_headers(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "shared.qdrant_utils.QdrantClient",
        lambda **kw: calls.append(kw) or kw,
    )
    client = create_qdrant_client(url="http://q", api_key="secret", headers={"X": "1"})
    assert client["api_key"] == "secret"
    assert "headers" not in calls[0]


def test_qdrant_utils_no_key_passes_headers(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "shared.qdrant_utils.QdrantClient",
        lambda **kw: calls.append(kw) or kw,
    )
    client = create_qdrant_client(url="http://q", headers={"X": "1"})
    assert client["headers"] == {"X": "1"}
    assert calls[0]["headers"] == {"X": "1"}


def test_qdrant_utils_typeerror_fallback(monkeypatch):
    calls = []

    def fake(**kw):
        calls.append(kw)
        if "headers" in kw:
            raise TypeError("headers unsupported")
        return kw

    monkeypatch.setattr("shared.qdrant_utils.QdrantClient", fake)
    client = create_qdrant_client(url="http://q", headers={"X": "1"})
    assert client["url"] == "http://q"
    assert len(calls) == 2
    assert "headers" not in calls[1]
