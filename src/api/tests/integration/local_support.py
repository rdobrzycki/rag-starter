from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from rag_api.config import LocalSettings


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_VECTOR_SIZE = 12


def build_test_settings(**overrides: Any) -> LocalSettings:
    defaults = dict(
        aws_region="us-east-1",
        bedrock_embed_model_id="local-embed-model",
        bedrock_llm_model_id="local-llm-model",
        qdrant_url="http://local-qdrant",
        qdrant_api_key=None,
        qdrant_collection="documents",
        similarity_threshold=0.0,
        top_k_default=5,
        top_k_max=20,
        enable_prometheus_metrics=False,
        enable_cloudwatch_metrics=False,
        cloudwatch_namespace="RAG/Test",
        max_batch_size=50,
        max_chunk_size=10000,
        feedback_log_level="INFO",
        rate_limit_enabled=True,
        rate_limit_query_per_minute=20,
        rate_limit_ingestion_per_minute=20,
        rate_limit_collection_per_minute=20,
        rate_limit_utility_per_minute=20,
        feedback_enabled=True,
        feedback_table_name="feedback-table",
        feedback_ttl_days=90,
    )
    defaults.update(overrides)
    return LocalSettings(**defaults)


def _embed_text(text: str, *, dimensions: int = _VECTOR_SIZE) -> list[float]:
    vector = [0.0] * dimensions
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % dimensions
        vector[index] += 1.0
    if not any(vector):
        vector[0] = 1.0
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_mag = math.sqrt(sum(a * a for a in left))
    right_mag = math.sqrt(sum(b * b for b in right))
    if left_mag == 0 or right_mag == 0:
        return 0.0
    return numerator / (left_mag * right_mag)


def _matches_filter(payload: dict[str, Any], query_filter: dict[str, Any] | None) -> bool:
    if not query_filter:
        return True
    must = query_filter.get("must", [])
    for clause in must:
        key = clause.get("key")
        expected = clause.get("match", {}).get("value")
        if payload.get(key) != expected:
            return False
    return True


class FakeBedrock:
    def embed(self, model_id: str, text: str) -> list[float]:
        return _embed_text(text)

    def invoke(self, model_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages", [])
        question = ""
        context = ""
        for message in messages:
            if message.get("role") != "user":
                continue
            for content in message.get("content", []):
                text = str(content.get("text", ""))
                if "QUESTION:\n" in text and "\n\nCONTEXT:\n" in text:
                    question, context = text.split("\n\nCONTEXT:\n", maxsplit=1)
                    question = question.replace("QUESTION:\n", "").strip()
                    context = context.strip()
        if context:
            answer = f"Local answer for '{question}' using {context[:120]}"
        else:
            answer = f"Local answer for '{question}'"
        return {"content": [{"type": "text", "text": answer}]}


class FakeEmbeddingProvider:
    def embed(self, text: str, *, model_id: str) -> list[float]:
        return _embed_text(text)


class FakeLLMProvider:
    def invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        model_id: str,
        temperature: float = 0,
    ) -> dict[str, Any]:
        return FakeBedrock().invoke(model_id, {"messages": messages, "temperature": temperature})


@dataclass
class _StoredCollection:
    size: int
    distance: Any
    points: dict[str, dict[str, Any]]


class InMemoryQdrant:
    def __init__(self, default_collection: str = "documents", vector_size: int = _VECTOR_SIZE):
        self._collections: dict[str, _StoredCollection] = {
            default_collection: _StoredCollection(
                size=vector_size,
                distance="Cosine",
                points={},
            )
        }

    def get_collections(self):
        return SimpleNamespace(
            collections=[SimpleNamespace(name=name) for name in sorted(self._collections)]
        )

    def create_collection(self, collection_name: str, vectors_config: Any):
        if collection_name in self._collections:
            raise Exception(f"Collection '{collection_name}' already exists")
        self._collections[collection_name] = _StoredCollection(
            size=int(getattr(vectors_config, "size", _VECTOR_SIZE)),
            distance=getattr(vectors_config, "distance", "Cosine"),
            points={},
        )

    def get_collection(self, collection_name: str):
        if collection_name not in self._collections:
            raise Exception(f"Collection '{collection_name}' not found")
        collection = self._collections[collection_name]
        vectors = SimpleNamespace(size=collection.size, distance=collection.distance)
        params = SimpleNamespace(vectors=vectors)
        config = SimpleNamespace(params=params)
        return SimpleNamespace(
            config=config,
            points_count=len(collection.points),
            status="green",
        )

    def delete_collection(self, collection_name: str):
        if collection_name not in self._collections:
            raise Exception(f"Collection '{collection_name}' not found")
        del self._collections[collection_name]

    def upsert(self, *, collection_name: str, points: list[dict[str, Any]]):
        if collection_name not in self._collections:
            vector_size = len(points[0].get("vector", [])) if points else _VECTOR_SIZE
            self._collections[collection_name] = _StoredCollection(
                size=vector_size,
                distance="Cosine",
                points={},
            )
        collection = self._collections[collection_name]
        for point in points:
            collection.points[str(point["id"])] = {
                "id": str(point["id"]),
                "vector": list(point.get("vector", [])),
                "payload": dict(point.get("payload", {})),
            }

    def delete(self, *, collection_name: str, points_selector: Any):
        collection = self._collections.get(collection_name)
        if collection is None:
            return SimpleNamespace(deleted=0)

        point_ids: list[str] = []
        if isinstance(points_selector, dict):
            filter_query = points_selector.get("filter")
            if filter_query:
                for point_id, point in list(collection.points.items()):
                    if _matches_filter(point["payload"], filter_query):
                        point_ids.append(point_id)
            else:
                point_ids = [str(value) for value in points_selector]
        elif isinstance(points_selector, list):
            point_ids = [str(value) for value in points_selector]
        elif hasattr(points_selector, "points"):
            point_ids = [str(value) for value in points_selector.points]

        deleted = 0
        for point_id in point_ids:
            if point_id in collection.points:
                del collection.points[point_id]
                deleted += 1
        return SimpleNamespace(deleted=deleted)

    def scroll(
        self,
        *,
        collection_name: str,
        scroll_filter: dict[str, Any] | None = None,
        limit: int = 100,
        with_payload: bool = True,
        with_vectors: bool = False,
        offset: int | None = None,
    ):
        collection = self._collections.get(collection_name)
        if collection is None:
            return [], None
        start = offset or 0
        points = [
            SimpleNamespace(
                id=point["id"],
                payload=dict(point["payload"]) if with_payload else None,
                vector=list(point["vector"]) if with_vectors else None,
            )
            for point in collection.points.values()
            if _matches_filter(point["payload"], scroll_filter)
        ]
        page = points[start : start + limit]
        next_offset = start + limit if start + limit < len(points) else None
        return page, next_offset

    def query_points(
        self,
        *,
        collection_name: str,
        query: list[float],
        limit: int,
        score_threshold: float,
        query_filter: dict[str, Any] | None = None,
        with_payload: bool = True,
    ):
        collection = self._collections.get(collection_name)
        if collection is None:
            raise Exception(f"Collection '{collection_name}' not found")

        hits = []
        for point in collection.points.values():
            payload = point["payload"]
            if not _matches_filter(payload, query_filter):
                continue
            score = _cosine_similarity(query, point["vector"])
            if score >= score_threshold:
                hits.append(
                    SimpleNamespace(
                        id=point["id"],
                        score=score,
                        payload=dict(payload) if with_payload else None,
                    )
                )
        hits.sort(key=lambda item: item.score, reverse=True)
        return SimpleNamespace(points=hits[:limit])

    def get_points_for_doc(
        self, doc_id: str, *, collection_name: str = "documents"
    ) -> list[dict[str, Any]]:
        collection = self._collections.get(collection_name)
        if collection is None:
            return []
        matches = [
            dict(point)
            for point in collection.points.values()
            if point["payload"].get("doc_id") == doc_id
        ]
        matches.sort(key=lambda point: point["payload"].get("chunk_index", 0))
        return matches


class InMemoryFeedbackService:
    def __init__(self):
        self._items: list[dict[str, Any]] = []
        self._clock = int(time.time() * 1000)

    def save_feedback(
        self,
        request_id: str,
        query: str,
        answer: str,
        rating: int | None = None,
        notes: str | None = None,
        expected: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        self._clock += 1
        item = {
            "request_id": request_id,
            "timestamp": self._clock,
            "query": query,
            "answer": answer,
        }
        if rating is not None:
            item["rating"] = rating
        if notes is not None:
            item["notes"] = notes
        if expected is not None:
            item["expected"] = expected
        if trace_id is not None:
            item["trace_id"] = trace_id
        self._items.append(item)
        return request_id

    def get_feedback(self, request_id: str) -> dict[str, Any] | None:
        matches = [item for item in self._items if item["request_id"] == request_id]
        if not matches:
            return None
        return sorted(matches, key=lambda item: item["timestamp"])[-1]

    def list_feedback(
        self, limit: int = 100, start_key: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        items = sorted(self._items, key=lambda item: item["timestamp"])
        start_index = 0
        if start_key is not None:
            for index, item in enumerate(items):
                if item["request_id"] == start_key.get("request_id") and item[
                    "timestamp"
                ] == start_key.get("timestamp"):
                    start_index = index + 1
                    break
        page = items[start_index : start_index + min(limit, 100)]
        if start_index + len(page) < len(items) and page:
            last = page[-1]
            last_key = {"request_id": last["request_id"], "timestamp": last["timestamp"]}
        else:
            last_key = None
        return {"items": page, "last_evaluated_key": last_key}

    def get_analytics(self, days_back: int = 30) -> dict[str, Any]:
        ratings = [item["rating"] for item in self._items if "rating" in item]
        distribution: dict[str, int] = {}
        for rating in ratings:
            distribution[str(rating)] = distribution.get(str(rating), 0) + 1
        return {
            "total_feedback": len(self._items),
            "avg_rating": (sum(ratings) / len(ratings)) if ratings else None,
            "rating_distribution": distribution,
            "period_days": days_back,
        }

    def delete_feedback(self, request_id: str) -> None:
        self._items = [item for item in self._items if item["request_id"] != request_id]


class CleanupTracker:
    def __init__(self, qdrant_client: InMemoryQdrant, feedback_service: InMemoryFeedbackService):
        self._qdrant_client = qdrant_client
        self._feedback_service = feedback_service
        self._document_ids: set[str] = set()
        self._collection_names: set[str] = set()
        self._feedback_ids: set[str] = set()

    def add_document_id(self, document_id: str) -> None:
        self._document_ids.add(document_id)

    def add_collection_name(self, collection_name: str) -> None:
        self._collection_names.add(collection_name)

    def add_feedback_id(self, feedback_id: str) -> None:
        self._feedback_ids.add(feedback_id)

    def cleanup(self) -> None:
        for document_id in self._document_ids:
            self._qdrant_client.delete(
                collection_name="documents",
                points_selector={
                    "filter": {"must": [{"key": "doc_id", "match": {"value": document_id}}]}
                },
            )
        for collection_name in self._collection_names:
            if collection_name != "documents":
                try:
                    self._qdrant_client.delete_collection(collection_name)
                except Exception:
                    pass
        for feedback_id in self._feedback_ids:
            self._feedback_service.delete_feedback(feedback_id)
