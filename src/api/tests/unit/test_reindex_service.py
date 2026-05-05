from __future__ import annotations

from types import SimpleNamespace

from rag_api.models import ChunkingConfig, DocumentIngestResponse
from rag_api.services.reindex import reindex_documents


class _FakeS3:
    def __init__(
        self, *, data: bytes = b"", content_type: str = "text/plain", should_fail: bool = False
    ):
        self.data = data
        self.content_type = content_type
        self.should_fail = should_fail

    def get_object(self, Bucket: str, Key: str):
        if self.should_fail:
            raise RuntimeError("s3 read failed")
        return {
            "Body": SimpleNamespace(read=lambda: self.data),
            "ContentType": self.content_type,
        }


class _FakeQdrant:
    def __init__(self, pages):
        self.pages = pages
        self.scroll_calls = 0
        self.deleted_doc_ids: list[str] = []

    def scroll(self, **kwargs):
        if self.scroll_calls >= len(self.pages):
            return [], None
        page = self.pages[self.scroll_calls]
        self.scroll_calls += 1
        return page

    def delete(self, *, points_selector, **kwargs):
        match = points_selector["filter"]["must"][0]["match"]["value"]
        self.deleted_doc_ids.append(match)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        aws_region="us-east-1",
        bedrock_embed_model_id="embed-model",
        qdrant_collection="documents",
    )


def test_reindex_uses_s3_source_text(monkeypatch):
    qc = _FakeQdrant(
        pages=[
            (
                [
                    {
                        "payload": {
                            "doc_id": "doc-1",
                            "source_uri": "s3://bucket/a.txt",
                            "chunk_index": 0,
                            "text": "old",
                        }
                    },
                ],
                None,
            )
        ]
    )
    captured = {}

    def fake_ingest_document(bedrock, qc, req, settings):
        captured["text"] = req.text
        return DocumentIngestResponse(document_id="doc-1", chunks_upserted=3, status="success")

    monkeypatch.setattr("rag_api.services.reindex.ingest_document", fake_ingest_document)

    response = reindex_documents(
        bedrock=object(),
        qc=qc,
        settings=_settings(),
        collection="documents",
        chunking=ChunkingConfig(chunk_size=2000, overlap=100),
        s3_client=_FakeS3(data=b"new from s3", content_type="text/plain"),
    )

    assert response.status == "success"
    assert response.documents_reindexed == 1
    assert response.chunks_created == 3
    assert captured["text"] == "new from s3"
    assert qc.deleted_doc_ids == ["doc-1"]


def test_reindex_falls_back_to_existing_chunks_when_s3_unavailable(monkeypatch):
    qc = _FakeQdrant(
        pages=[
            (
                [
                    {
                        "payload": {
                            "doc_id": "doc-1",
                            "source_uri": "test://doc",
                            "chunk_index": 1,
                            "text": "chunk-b",
                        }
                    },
                    {
                        "payload": {
                            "doc_id": "doc-1",
                            "source_uri": "test://doc",
                            "chunk_index": 0,
                            "text": "chunk-a",
                        }
                    },
                ],
                None,
            )
        ]
    )
    captured = {}

    def fake_ingest_document(bedrock, qc, req, settings):
        captured["text"] = req.text
        return DocumentIngestResponse(document_id="doc-1", chunks_upserted=2, status="success")

    monkeypatch.setattr("rag_api.services.reindex.ingest_document", fake_ingest_document)

    response = reindex_documents(
        bedrock=object(),
        qc=qc,
        settings=_settings(),
        collection="documents",
        s3_client=_FakeS3(should_fail=True),
    )

    assert response.status == "success"
    assert response.documents_reindexed == 1
    assert captured["text"] == "chunk-a\n\nchunk-b"


def test_reindex_returns_partial_on_per_document_failures(monkeypatch):
    qc = _FakeQdrant(
        pages=[
            (
                [
                    {
                        "payload": {
                            "doc_id": "doc-1",
                            "source_uri": "test://doc-1",
                            "chunk_index": 0,
                            "text": "one",
                        }
                    },
                    {
                        "payload": {
                            "doc_id": "doc-2",
                            "source_uri": "test://doc-2",
                            "chunk_index": 0,
                            "text": "two",
                        }
                    },
                ],
                None,
            )
        ]
    )

    def fake_ingest_document(bedrock, qc, req, settings):
        if req.source_uri.endswith("doc-2"):
            raise RuntimeError("embed failure")
        return DocumentIngestResponse(document_id="doc-1", chunks_upserted=1, status="success")

    monkeypatch.setattr("rag_api.services.reindex.ingest_document", fake_ingest_document)

    response = reindex_documents(
        bedrock=object(),
        qc=qc,
        settings=_settings(),
        collection="documents",
        s3_client=_FakeS3(should_fail=True),
    )

    assert response.status == "partial"
    assert response.documents_reindexed == 1
    assert response.chunks_created == 1


def test_reindex_returns_success_when_no_documents_match():
    qc = _FakeQdrant(pages=[([], None)])

    response = reindex_documents(
        bedrock=object(),
        qc=qc,
        settings=_settings(),
        collection="documents",
        s3_client=_FakeS3(),
    )

    assert response.status == "success"
    assert response.documents_reindexed == 0
    assert response.chunks_created == 0
