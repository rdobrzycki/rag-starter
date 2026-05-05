from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from rag_api.bedrock import Bedrock
from rag_api.config import LocalSettings, load_local_settings
from rag_api.dependencies import get_bedrock, get_feedback_service, get_qdrant, get_settings
from rag_api.exceptions.handlers import general_exception_handler, http_exception_handler
from rag_api.middleware.audit_logging import _log_request, _log_response, audit_logging_middleware
from rag_api.middleware.correlation import add_correlation_id
from rag_api.middleware.rate_limiting import rate_limiting_middleware
from rag_api.models import (
    ChunkingConfig,
    CollectionCreateRequest,
    DocumentBatchIngestRequest,
    DocumentDeleteResponse,
    DocumentIngestResponse,
    DocumentIngestRequest,
    EmbedRequest,
    FeedbackRequest,
    QueryRequest,
    QueryResponse,
    ReindexRequest,
    ReindexResponse,
)
from rag_api.prompts import SYSTEM_PROMPT
from rag_api.providers.base import EmbeddingProvider, LLMProvider
from rag_api.qdrant_client import make_qdrant
from rag_api.rag.context_builder import build_context
from rag_api.rag.retrieval import Retrieved
from rag_api.routers.collections import (
    create_collection,
    delete_collection,
    get_collection_info,
    list_collections,
)
from rag_api.routers.core import health, query, ready_check
from rag_api.routers.documents import (
    delete_document,
    ingest_batch_documents,
    ingest_single_document,
    reindex_documents,
)
from rag_api.routers.utilities import embed_text, get_metrics, submit_feedback
from rag_api.services.ingestion import ingest_document


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(**overrides) -> LocalSettings:
    defaults = dict(
        aws_region="us-east-1",
        bedrock_embed_model_id="embed-model",
        bedrock_llm_model_id="llm-model",
        qdrant_url="http://localhost:6333",
        qdrant_api_key=None,
        qdrant_collection="documents",
        similarity_threshold=0.7,
        top_k_default=5,
        top_k_max=20,
        enable_prometheus_metrics=False,
        enable_cloudwatch_metrics=False,
        cloudwatch_namespace="RAG/Test",
        max_batch_size=50,
        max_chunk_size=10000,
        feedback_log_level="INFO",
        rate_limit_enabled=True,
        rate_limit_query_per_minute=100,
        rate_limit_ingestion_per_minute=30,
        rate_limit_collection_per_minute=50,
        rate_limit_utility_per_minute=60,
        feedback_enabled=True,
        feedback_table_name="feedback-table",
        feedback_ttl_days=90,
    )
    defaults.update(overrides)
    return LocalSettings(**defaults)


class _StubMetrics:
    """Minimal metrics stub used by router tests."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def record_query(self, **kw):
        self.calls.append(("query", kw))

    def record_error(self, **kw):
        self.calls.append(("error", kw))

    def record_document_ingestion(self, **kw):
        self.calls.append(("doc_ingest", kw))

    def record_bedrock_call(self, **kw):
        self.calls.append(("bedrock", kw))

    def record_qdrant_call(self, **kw):
        self.calls.append(("qdrant", kw))


# ===================================================================
# rag_api.config
# ===================================================================


def test_load_local_settings_defaults(monkeypatch):
    for var in ("BEDROCK_EMBED_MODEL_ID", "QDRANT_COLLECTION", "SIMILARITY_THRESHOLD"):
        monkeypatch.delenv(var, raising=False)
    settings = load_local_settings()
    assert settings.bedrock_embed_model_id == "amazon.titan-embed-text-v2:0"
    assert settings.qdrant_collection == "documents"
    assert settings.similarity_threshold == 0.70


def test_load_local_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("QDRANT_COLLECTION", "custom-col")
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.85")
    monkeypatch.setenv("ENABLE_PROMETHEUS_METRICS", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("QDRANT_API_KEY", "")
    settings = load_local_settings()
    assert settings.qdrant_collection == "custom-col"
    assert settings.similarity_threshold == 0.85
    assert settings.enable_prometheus_metrics is True
    assert settings.rate_limit_enabled is False
    assert settings.qdrant_api_key is None  # empty string → None


# ===================================================================
# rag_api.dependencies
# ===================================================================


def test_dependencies_build_all_clients(monkeypatch):
    settings = _settings()
    get_settings.cache_clear()

    monkeypatch.setattr("rag_api.dependencies.load_local_settings", lambda: settings)

    calls: dict[str, object] = {}

    def fake_make_qdrant(url, api_key):
        calls["qdrant_url"] = url
        return "qc"

    class _Table:
        pass

    class _Dynamo:
        def Table(self, name):
            calls["table_name"] = name
            return _Table()

    monkeypatch.setattr("rag_api.dependencies.make_qdrant", fake_make_qdrant)
    monkeypatch.setattr("rag_api.dependencies.boto3.resource", lambda *_a, **_kw: _Dynamo())
    monkeypatch.setattr(
        "rag_api.dependencies.boto3.client",
        lambda *_a, **_kw: SimpleNamespace(),
    )

    assert get_settings() == settings
    assert get_qdrant(settings) == "qc"
    assert calls["qdrant_url"] == "http://localhost:6333"

    svc = get_feedback_service(settings)
    assert svc.ttl_days == 90
    assert calls["table_name"] == "feedback-table"


def test_get_bedrock_dependency(monkeypatch):
    settings = _settings()
    regions: list[str] = []

    monkeypatch.setattr(
        "rag_api.dependencies.boto3.client",
        lambda *_a, **kw: SimpleNamespace(region=kw.get("region_name")),
    )
    monkeypatch.setattr(
        "rag_api.dependencies.get_cloudwatch_metrics",
        lambda **_kw: None,
    )

    def patched_init(self, region, metrics=None):
        regions.append(region)
        self._runtime = SimpleNamespace()
        self._metrics = metrics

    monkeypatch.setattr(Bedrock, "__init__", patched_init)
    bedrock = get_bedrock(settings)
    assert isinstance(bedrock, Bedrock)
    assert regions == ["us-east-1"]


# ===================================================================
# rag_api.exceptions.handlers
# ===================================================================


def test_http_exception_handler_includes_correlation():
    from shared.correlation import reset_correlation_id

    reset_correlation_id()
    req = SimpleNamespace(state=SimpleNamespace(correlation_id="cid-1"))
    response = asyncio.run(
        http_exception_handler(req, HTTPException(status_code=400, detail="bad"))
    )
    assert response.status_code == 400
    assert b'"correlation_id":"cid-1"' in response.body


def test_general_exception_handler_includes_detail():
    from shared.correlation import reset_correlation_id

    reset_correlation_id()
    req = SimpleNamespace(state=SimpleNamespace(correlation_id="cid-2"))
    response = asyncio.run(general_exception_handler(req, ValueError("boom")))
    assert response.status_code == 500
    assert b"Internal server error" in response.body
    assert b"boom" in response.body


# ===================================================================
# rag_api.middleware.correlation  (happy + 404 override)
# ===================================================================


def test_correlation_middleware_sets_request_id_header(monkeypatch):
    req = SimpleNamespace(headers={}, state=SimpleNamespace())

    async def call_next(_request):
        return SimpleNamespace(status_code=200, headers={})

    monkeypatch.setattr(
        "rag_api.middleware.correlation.get_or_create_correlation_id",
        lambda _hdr: "cid-123",
    )
    monkeypatch.setattr(
        "rag_api.middleware.correlation.set_correlation_id",
        lambda _cid: None,
    )

    response = asyncio.run(add_correlation_id(req, call_next))
    assert response.headers["X-Request-ID"] == "cid-123"
    assert req.state.correlation_id == "cid-123"


def test_correlation_middleware_rewrites_404_body(monkeypatch):
    """When downstream returns 404, middleware replaces body with JSON including correlation_id."""
    req = SimpleNamespace(headers={}, state=SimpleNamespace())

    async def call_next(_request):
        return SimpleNamespace(status_code=404, headers={})

    monkeypatch.setattr(
        "rag_api.middleware.correlation.get_or_create_correlation_id",
        lambda _hdr: "cid-404",
    )
    monkeypatch.setattr(
        "rag_api.middleware.correlation.set_correlation_id",
        lambda _cid: None,
    )

    response = asyncio.run(add_correlation_id(req, call_next))
    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "cid-404"
    assert b"cid-404" in response.body


# ===================================================================
# rag_api.middleware.rate_limiting  (blocked + allowed + no-limit)
# ===================================================================


def _rate_req():
    return SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        url=SimpleNamespace(path="/query"),
        state=SimpleNamespace(correlation_id="cid-rate"),
    )


def test_rate_limiting_middleware_blocks_request(monkeypatch):
    class _Limiter:
        config = {}

        def is_allowed(self, *_a, **_kw):
            return (False, 0, 9999999999.0)

    monkeypatch.setattr("rag_api.middleware.rate_limiting.get_endpoint_limit", lambda *_a: 1)
    monkeypatch.setattr("rag_api.middleware.rate_limiting.get_correlation_id", lambda: "cid-rate")

    async def call_next(_r):
        return SimpleNamespace(headers={})

    response = asyncio.run(rate_limiting_middleware(_rate_req(), call_next, _Limiter()))
    assert response.status_code == 429
    assert response.headers["X-RateLimit-Limit"] == "1"
    assert response.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limiting_middleware_allows_request(monkeypatch):
    class _Limiter:
        config = {}

        def is_allowed(self, *_a, **_kw):
            return (True, 99, 1700000000.0)

    monkeypatch.setattr("rag_api.middleware.rate_limiting.get_endpoint_limit", lambda *_a: 100)

    async def call_next(_r):
        return SimpleNamespace(headers={}, status_code=200)

    response = asyncio.run(rate_limiting_middleware(_rate_req(), call_next, _Limiter()))
    assert response.headers["X-RateLimit-Remaining"] == "99"
    assert response.headers["X-RateLimit-Limit"] == "100"


def test_rate_limiting_middleware_no_limit_passthrough(monkeypatch):
    monkeypatch.setattr("rag_api.middleware.rate_limiting.get_endpoint_limit", lambda *_a: None)

    sentinel = SimpleNamespace(headers={}, status_code=200)

    async def call_next(_r):
        return sentinel

    limiter = SimpleNamespace(config={})
    response = asyncio.run(rate_limiting_middleware(_rate_req(), call_next, limiter))
    assert response is sentinel


# ===================================================================
# rag_api.prompts / rag_api.providers.base
# ===================================================================


def test_prompts_system_prompt_content():
    assert "REFUSE" in SYSTEM_PROMPT
    assert "CONTEXT" in SYSTEM_PROMPT


def test_provider_protocols_structural_subtyping():
    """A class that implements the right methods satisfies the Protocol."""

    class MyEmbedder:
        def embed(self, text: str, *, model_id: str) -> list[float]:
            return [0.1]

    class MyLLM:
        def invoke(self, messages, *, model_id, temperature=0):
            return {}

    assert isinstance(MyEmbedder(), MyEmbedder)
    assert isinstance(MyLLM(), MyLLM)
    assert callable(getattr(EmbeddingProvider, "embed", None))
    assert callable(getattr(LLMProvider, "invoke", None))


# ===================================================================
# rag_api.qdrant_client
# ===================================================================


def test_make_qdrant_delegates_to_shared_factory(monkeypatch):
    monkeypatch.setattr(
        "rag_api.qdrant_client.build_correlation_headers",
        lambda: {"X-Request-ID": "cid-q"},
    )
    monkeypatch.setattr(
        "rag_api.qdrant_client.create_qdrant_client",
        lambda **kw: kw,
    )
    client = make_qdrant("http://qdrant", "api")
    assert client["url"] == "http://qdrant"
    assert client["headers"]["X-Request-ID"] == "cid-q"


# ===================================================================
# rag_api.rag.context_builder  (single, multi, empty, truncation)
# ===================================================================


def _chunk(cid="c1", score=0.9, text="hello", uri="s3://a/b"):
    return Retrieved(chunk_id=cid, score=score, text=text, source_uri=uri)


def test_context_builder_truncates_long_text():
    ctx = build_context([_chunk(text="x" * 30)], max_chunks=1, max_chars_per_chunk=10)
    assert "xxxxxxxxxx" in ctx
    assert "\u2026" in ctx  # ellipsis at truncation point


def test_context_builder_multiple_chunks_separated():
    ctx = build_context(
        [_chunk(cid="c1", text="aaa"), _chunk(cid="c2", text="bbb")],
        max_chunks=5,
    )
    assert "---" in ctx
    assert "c1" in ctx and "c2" in ctx


def test_context_builder_empty_chunks():
    assert build_context([], max_chunks=5) == ""


# ===================================================================
# rag_api.bedrock  (happy path + metrics recording)
# ===================================================================


def test_bedrock_embed_and_invoke(monkeypatch):
    class Runtime:
        def invoke_model(self, *, modelId, body):
            payload = b'{"embedding":[0.1,0.2]}' if "inputText" in body else b'{"ok":true}'
            return {"body": io.BytesIO(payload)}

    monkeypatch.setattr("rag_api.bedrock.boto3.client", lambda *_a, **_kw: Runtime())
    metrics = _StubMetrics()
    bedrock = Bedrock(region="us-east-1", metrics=metrics)
    assert bedrock.embed("embed-model", "hello") == [0.1, 0.2]
    assert bedrock.invoke("llm-model", {"messages": []}) == {"ok": True}

    bedrock_calls = [c for c in metrics.calls if c[0] == "bedrock"]
    assert len(bedrock_calls) == 2
    assert bedrock_calls[0][1]["success"] is True
    assert bedrock_calls[1][1]["operation"] == "invoke"


# ===================================================================
# rag_api.middleware.audit_logging
# ===================================================================


def test_audit_logging_request_and_response(monkeypatch):
    records = []
    monkeypatch.setattr(
        "rag_api.middleware.audit_logging.logger.handle",
        lambda record: records.append(record),
    )

    class Req:
        method = "POST"
        url = SimpleNamespace(path="/query")
        client = SimpleNamespace(host="127.0.0.1")
        query_params = {"q": "x"}
        headers = {"content-type": "application/json", "authorization": "secret"}

        async def body(self):
            return b'{"token":"abc"}'

    class Resp:
        status_code = 200
        headers = {"content-type": "application/json"}

        async def _iter(self):
            yield b'{"ok": true}'

        body_iterator = _iter(None)  # type: ignore[misc]

    asyncio.run(_log_request(Req()))
    asyncio.run(_log_response(Req(), Resp(), start_time=0.0))

    assert len(records) == 2
    assert getattr(records[0], "event_type") == "http_request"
    assert getattr(records[1], "event_type") == "http_response"
    assert getattr(records[1], "latency_ms") > 0


def test_audit_logging_middleware_orchestrates(monkeypatch):
    log_calls: list[str] = []

    async def fake_log_request(_req):
        log_calls.append("req")

    async def fake_log_response(_req, _resp, start_time):
        log_calls.append("resp")

    monkeypatch.setattr("rag_api.middleware.audit_logging._log_request", fake_log_request)
    monkeypatch.setattr("rag_api.middleware.audit_logging._log_response", fake_log_response)

    sentinel = SimpleNamespace(status_code=200)

    async def call_next(_r):
        return sentinel

    resp = asyncio.run(audit_logging_middleware(SimpleNamespace(), call_next))
    assert resp is sentinel
    assert log_calls == ["req", "resp"]


# ===================================================================
# rag_api.routers.core  (health, ready, query happy + error)
# ===================================================================


def test_core_router_health():
    assert health() == {"ok": True}


def test_core_router_ready_check():
    settings = _settings()

    class QC:
        def get_collection(self, _name):
            return None

    class B:
        def embed(self, *_a, **_kw):
            return [0.1]

    response = SimpleNamespace(status_code=200)
    ready = ready_check(response, settings, QC(), B())
    assert ready.ready is True
    assert ready.checks["qdrant"] is True


def test_core_router_query_success(monkeypatch):
    settings = _settings()
    metrics = _StubMetrics()
    monkeypatch.setattr("rag_api.routers.core.get_cloudwatch_metrics", lambda **_k: metrics)
    monkeypatch.setattr(
        "rag_api.routers.core.answer",
        lambda *_a, **_kw: QueryResponse(answer="a", refused=False, sources=[]),
    )
    result = query(QueryRequest(query="hello"), settings)
    assert result.answer == "a"
    assert any(c[1].get("status") == "success" for c in metrics.calls)


def test_core_router_query_error(monkeypatch):
    settings = _settings()
    metrics = _StubMetrics()
    monkeypatch.setattr("rag_api.routers.core.get_cloudwatch_metrics", lambda **_k: metrics)
    monkeypatch.setattr("rag_api.routers.core.answer", Mock(side_effect=RuntimeError("fail")))

    with pytest.raises(HTTPException) as exc_info:
        query(QueryRequest(query="hello"), settings)
    assert exc_info.value.status_code == 500
    assert any(c[0] == "error" for c in metrics.calls)


# ===================================================================
# rag_api.routers.collections  (happy + error paths)
# ===================================================================


def _stub_qc(**extra):
    defaults = dict(
        get_collections=lambda: SimpleNamespace(collections=[SimpleNamespace(name="docs")]),
        create_collection=lambda **_kw: None,
        get_collection=lambda _n: SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=1024, distance="Cosine"))
            ),
            points_count=3,
            status="green",
        ),
        delete_collection=lambda _n: None,
        delete=lambda **_kw: SimpleNamespace(deleted=2),
    )
    defaults.update(extra)
    return SimpleNamespace(**defaults)


def test_collection_list_and_create():
    qc = _stub_qc()
    assert list_collections(qc).collections == ["docs"]
    assert create_collection(CollectionCreateRequest(name="abc"), qc).status == "created"


def test_collection_create_already_exists():
    def raise_exists(**_kw):
        raise Exception("Collection already exists")

    qc = _stub_qc(create_collection=raise_exists)
    result = create_collection(CollectionCreateRequest(name="abc"), qc)
    assert result.status == "already_exists"


def test_collection_get_info_and_delete():
    qc = _stub_qc()
    info = get_collection_info("abc", qc)
    assert info.points_count == 3
    assert delete_collection("abc", qc) is None


def test_collection_get_info_not_found():
    def raise_not_found(_n):
        raise Exception("not found")

    qc = _stub_qc(get_collection=raise_not_found)
    with pytest.raises(HTTPException) as exc_info:
        get_collection_info("missing", qc)
    assert exc_info.value.status_code == 404


# ===================================================================
# rag_api.routers.documents  (single ingest, batch, delete, reindex)
# ===================================================================


def test_document_delete():
    qc = _stub_qc()
    settings = _settings()
    deleted: DocumentDeleteResponse = delete_document("doc1", None, settings, qc)
    assert deleted.status == "success"
    assert deleted.chunks_deleted == 2


def test_documents_single_ingest(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(
        "rag_api.routers.documents.get_cloudwatch_metrics", lambda **_kw: _StubMetrics()
    )
    monkeypatch.setattr(
        "rag_api.routers.documents.ingest_document",
        lambda *_a, **_kw: DocumentIngestResponse(
            status="success", document_id="d1", chunks_upserted=1
        ),
    )
    res = ingest_single_document(
        DocumentIngestRequest(source_uri="s3://a/doc.txt", text="hi"),
        settings,
        SimpleNamespace(),
        SimpleNamespace(),
    )
    assert res.document_id == "d1"


def test_documents_batch_ingest(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(
        "rag_api.routers.documents.get_cloudwatch_metrics", lambda **_kw: _StubMetrics()
    )
    monkeypatch.setattr(
        "rag_api.routers.documents.ingest_document",
        lambda *_a, **_kw: DocumentIngestResponse(
            status="success", document_id="d1", chunks_upserted=1
        ),
    )
    req = DocumentBatchIngestRequest(
        documents=[DocumentIngestRequest(source_uri="s3://a/doc.txt", text="hello")]
    )
    res = ingest_batch_documents(req, settings, SimpleNamespace(), SimpleNamespace())
    assert res.total_success == 1
    assert res.total_failed == 0


def test_documents_reindex(monkeypatch):
    settings = _settings()
    monkeypatch.setattr(
        "rag_api.routers.documents.get_cloudwatch_metrics", lambda **_kw: _StubMetrics()
    )
    monkeypatch.setattr(
        "rag_api.routers.documents.run_reindex_documents",
        lambda **_kw: ReindexResponse(documents_reindexed=2, chunks_created=4, status="success"),
    )
    req = ReindexRequest(collection="docs")
    res = reindex_documents(req, settings, SimpleNamespace(), SimpleNamespace())
    assert res.documents_reindexed == 2


# ===================================================================
# rag_api.routers.utilities  (embed, metrics, submit_feedback)
# ===================================================================


def test_utilities_embed():
    bedrock = SimpleNamespace(embed=lambda *_a: [1.0, 2.0])
    emb = embed_text(EmbedRequest(text="hello"), _settings(), bedrock)
    assert emb.dimension == 2


def test_utilities_metrics_disabled():
    with pytest.raises(HTTPException) as exc_info:
        get_metrics(_settings(enable_prometheus_metrics=False))
    assert exc_info.value.status_code == 404


def test_utilities_submit_feedback():
    svc = SimpleNamespace(save_feedback=Mock())
    settings = _settings()
    req = FeedbackRequest(query="q", answer="a", rating=5)
    resp = submit_feedback(req, settings, svc, x_request_id="req-x")
    assert resp.feedback_id == "req-x"
    assert resp.status == "recorded"
    svc.save_feedback.assert_called_once()


# ===================================================================
# rag_api.services.ingestion
# ===================================================================


def test_ingestion_service_chunking_and_upsert():
    bedrock = SimpleNamespace(embed=lambda *_args: [0.1, 0.2])
    captured = {}

    class QC:
        def upsert(self, **kwargs):
            captured.update(kwargs)

    settings = _settings()
    req = DocumentIngestRequest(
        source_uri="s3://bucket/doc.txt",
        text="hello world",
        chunking=ChunkingConfig(chunk_size=100, overlap=0),
    )
    out = ingest_document(bedrock, QC(), req, settings)
    assert out.status == "success"
    assert out.chunks_upserted > 0
    assert captured["collection_name"] == settings.qdrant_collection
    points = captured["points"]
    assert all("doc_id" in p["payload"] for p in points)
