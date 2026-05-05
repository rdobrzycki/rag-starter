"""Local integration tests for feedback endpoints."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.timeout(120)]


def test_feedback_post_records_basic_feedback(api_client, cleanup_tracker):
    response = api_client.post(
        "/feedback",
        json={"query": "What is machine learning?", "answer": "A subset of AI.", "rating": 5},
    )

    assert response.status_code == 201
    cleanup_tracker.add_feedback_id(response.json()["feedback_id"])
    assert response.json()["status"] == "recorded"


def test_feedback_post_accepts_optional_fields(api_client, cleanup_tracker):
    response = api_client.post(
        "/feedback",
        json={
            "query": "Explain neural networks",
            "answer": "Neural networks are layered models.",
            "rating": 4,
            "expected": "More examples",
            "notes": "Good answer",
            "trace_id": "trace-12345",
        },
    )

    assert response.status_code == 201
    feedback_id = response.json()["feedback_id"]
    cleanup_tracker.add_feedback_id(feedback_id)

    stored = api_client.get(f"/feedback/{feedback_id}")
    assert stored.status_code == 200
    assert stored.json()["trace_id"] == "trace-12345"


def test_feedback_post_without_rating_is_allowed(api_client, cleanup_tracker):
    response = api_client.post(
        "/feedback",
        json={"query": "What is AI?", "answer": "AI stands for..."},
    )

    assert response.status_code == 201
    cleanup_tracker.add_feedback_id(response.json()["feedback_id"])


def test_feedback_rating_validation_rejects_out_of_range(api_client):
    assert (
        api_client.post("/feedback", json={"query": "q", "answer": "a", "rating": 0}).status_code
        == 422
    )
    assert (
        api_client.post("/feedback", json={"query": "q", "answer": "a", "rating": 6}).status_code
        == 422
    )


def test_feedback_ids_are_unique_without_request_header(api_client, cleanup_tracker):
    first = api_client.post("/feedback", json={"query": "q", "answer": "a"})
    second = api_client.post("/feedback", json={"query": "q", "answer": "a"})

    assert first.json()["feedback_id"] != second.json()["feedback_id"]
    cleanup_tracker.add_feedback_id(first.json()["feedback_id"])
    cleanup_tracker.add_feedback_id(second.json()["feedback_id"])


def test_feedback_list_and_pagination(api_client, cleanup_tracker):
    created_ids = []
    for index in range(3):
        response = api_client.post(
            "/feedback",
            json={"query": f"Query {index}", "answer": f"Answer {index}", "rating": 4},
        )
        created_ids.append(response.json()["feedback_id"])
        cleanup_tracker.add_feedback_id(response.json()["feedback_id"])

    response = api_client.get("/feedback?limit=2")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["last_evaluated_key"] is not None
    returned_ids = {item["request_id"] for item in data["items"]}
    assert returned_ids.issubset(set(created_ids))


def test_feedback_get_by_request_id(api_client, cleanup_tracker):
    post_response = api_client.post(
        "/feedback",
        json={"query": "Get test", "answer": "Get test answer", "rating": 4},
        headers={"X-Request-ID": "req-test-123"},
    )

    feedback_id = post_response.json()["feedback_id"]
    cleanup_tracker.add_feedback_id(feedback_id)

    response = api_client.get(f"/feedback/{feedback_id}")

    assert response.status_code == 200
    assert response.json()["request_id"] == "req-test-123"
    assert response.json()["rating"] == 4


def test_feedback_analytics_summarizes_local_feedback(api_client, cleanup_tracker):
    for rating in [5, 4, 5, 3]:
        response = api_client.post(
            "/feedback",
            json={"query": f"Query {rating}", "answer": f"Answer {rating}", "rating": rating},
        )
        cleanup_tracker.add_feedback_id(response.json()["feedback_id"])

    response = api_client.get("/feedback/analytics?days=30")

    assert response.status_code == 200
    data = response.json()
    assert data["total_feedback"] >= 4
    assert data["avg_rating"] == pytest.approx(4.25)
    assert data["rating_distribution"] == {"5": 2, "4": 1, "3": 1}
