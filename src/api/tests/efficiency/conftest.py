"""Pytest fixtures for RAG efficiency tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

pytest_plugins = []


def pytest_configure(config):
    config.addinivalue_line("markers", "efficiency: RAG efficiency/quality tests (require API)")


def _fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def efficiency_api_url() -> str:
    """Base URL for the RAG API (e.g. http://localhost:8000)."""
    return os.environ.get("EFFICIENCY_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def efficiency_client(efficiency_api_url: str) -> httpx.Client:
    """HTTP client for efficiency tests. Targets deployed or local API."""
    return httpx.Client(base_url=efficiency_api_url, timeout=60.0)


@pytest.fixture(scope="session")
def test_cases() -> list[dict]:
    """Load Q&A test cases from fixtures/test_cases.json."""
    path = _fixtures_dir() / "test_cases.json"
    with path.open() as f:
        return json.load(f)
