"""Local integration tests for collection routes."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_list_collections_returns_default_collection(api_client):
    response = api_client.get("/collections")

    assert response.status_code == 200
    assert response.json() == {"collections": ["documents"]}


def test_create_collection_and_fetch_info(api_client, cleanup_tracker):
    response = api_client.post(
        "/collections",
        json={"name": "local-collection", "vector_size": 256, "distance": "Cosine"},
    )

    assert response.status_code == 201
    assert response.json() == {"name": "local-collection", "status": "created"}
    cleanup_tracker.add_collection_name("local-collection")

    info_response = api_client.get("/collections/local-collection")
    assert info_response.status_code == 200
    assert info_response.json() == {
        "name": "local-collection",
        "vector_size": 256,
        "distance": "Cosine",
        "points_count": 0,
        "status": "green",
    }


def test_create_collection_is_idempotent(api_client, cleanup_tracker):
    payload = {"name": "idempotent-collection", "vector_size": 512, "distance": "Dot"}

    first = api_client.post("/collections", json=payload)
    second = api_client.post("/collections", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["status"] == "already_exists"
    cleanup_tracker.add_collection_name("idempotent-collection")


def test_create_collection_supports_distance_options(api_client, cleanup_tracker):
    euclid = api_client.post(
        "/collections",
        json={"name": "euclid-collection", "vector_size": 300, "distance": "Euclid"},
    )
    dot = api_client.post(
        "/collections",
        json={"name": "dot-collection", "vector_size": 300, "distance": "Dot"},
    )

    assert euclid.status_code == 201
    assert dot.status_code == 201
    cleanup_tracker.add_collection_name("euclid-collection")
    cleanup_tracker.add_collection_name("dot-collection")


def test_create_collection_validation_rejects_bad_name_and_size(api_client):
    assert (
        api_client.post(
            "/collections",
            json={"name": "invalid name", "vector_size": 128},
        ).status_code
        == 422
    )
    assert (
        api_client.post("/collections", json={"name": "test", "vector_size": 50}).status_code == 422
    )
    assert (
        api_client.post(
            "/collections",
            json={"name": "test", "vector_size": 10000},
        ).status_code
        == 422
    )


def test_get_collection_info_returns_not_found_for_unknown_collection(api_client):
    response = api_client.get("/collections/missing-collection")

    assert response.status_code == 404
    assert response.json()["correlation_id"]


def test_delete_collection_removes_it(api_client):
    create = api_client.post(
        "/collections",
        json={"name": "delete-me", "vector_size": 128, "distance": "Cosine"},
    )
    assert create.status_code == 201

    response = api_client.delete("/collections/delete-me")
    assert response.status_code == 204

    missing = api_client.get("/collections/delete-me")
    assert missing.status_code == 404


def test_delete_collection_unknown_collection_returns_error(api_client):
    response = api_client.delete("/collections/not-real")

    assert response.status_code == 500
