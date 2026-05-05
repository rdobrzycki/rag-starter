from __future__ import annotations

import pytest

from rag_api.rag.retrieval import ensure_collection


class _QdrantMissingThenCreate:
    def __init__(self) -> None:
        self.created = False

    def get_collection(self, _name: str) -> None:
        raise Exception("Collection documents not found")

    def create_collection(self, **_kwargs) -> None:
        self.created = True


class _QdrantAdminRestricted:
    def __init__(self) -> None:
        self.create_called = False

    def get_collection(self, _name: str) -> None:
        raise Exception("Global access is required for this operation")

    def create_collection(self, **_kwargs) -> None:
        self.create_called = True


class _QdrantUnexpectedError:
    def get_collection(self, _name: str) -> None:
        raise RuntimeError("socket timeout")

    def create_collection(self, **_kwargs) -> None:
        raise AssertionError("create_collection should not be called")


def test_ensure_collection_creates_on_missing_collection() -> None:
    qc = _QdrantMissingThenCreate()

    ensure_collection(qc, "documents")

    assert qc.created is True


def test_ensure_collection_skips_when_admin_scope_restricted() -> None:
    qc = _QdrantAdminRestricted()

    ensure_collection(qc, "documents")

    assert qc.create_called is False


def test_ensure_collection_raises_on_unexpected_precheck_error() -> None:
    qc = _QdrantUnexpectedError()

    with pytest.raises(RuntimeError, match="socket timeout"):
        ensure_collection(qc, "documents")
