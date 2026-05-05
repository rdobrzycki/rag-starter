"""Unit tests for FeedbackService."""

import pytest
from unittest.mock import Mock
from rag_api.services.feedback_service import FeedbackService


@pytest.fixture
def mock_table():
    """Create mock DynamoDB table."""
    return Mock()


@pytest.fixture
def feedback_service(mock_table):
    """Create FeedbackService with mocked table."""
    return FeedbackService(mock_table, ttl_days=90)


def test_save_feedback_basic(feedback_service, mock_table):
    """Test saving basic feedback."""
    feedback_service.save_feedback(
        request_id="req-123",
        query="What is AI?",
        answer="AI is...",
        rating=5,
    )

    mock_table.put_item.assert_called_once()
    call_args = mock_table.put_item.call_args[1]["Item"]
    assert call_args["request_id"] == "req-123"
    assert call_args["query"] == "What is AI?"
    assert call_args["answer"] == "AI is..."
    assert call_args["rating"] == 5
    assert "timestamp" in call_args
    assert "ttl" in call_args


def test_save_feedback_all_fields(feedback_service, mock_table):
    """Test saving feedback with all optional fields."""
    feedback_service.save_feedback(
        request_id="req-123",
        query="What is AI?",
        answer="AI is...",
        rating=4,
        notes="Good answer",
        expected="More detailed",
        trace_id="trace-456",
    )

    call_args = mock_table.put_item.call_args[1]["Item"]
    assert call_args["notes"] == "Good answer"
    assert call_args["expected"] == "More detailed"
    assert call_args["trace_id"] == "trace-456"


def test_save_feedback_error_handling(feedback_service, mock_table):
    """Test error handling when save fails."""
    mock_table.put_item.side_effect = Exception("DynamoDB error")

    with pytest.raises(Exception):
        feedback_service.save_feedback(
            request_id="req-123",
            query="Test",
            answer="Test",
        )


def test_get_feedback_found(feedback_service, mock_table):
    """Test retrieving existing feedback."""
    mock_table.query.return_value = {"Items": [{"request_id": "req-123", "query": "Test"}]}

    result = feedback_service.get_feedback("req-123")
    assert result is not None
    assert result["request_id"] == "req-123"


def test_get_feedback_not_found(feedback_service, mock_table):
    """Test retrieving non-existent feedback."""
    mock_table.query.return_value = {"Items": []}

    result = feedback_service.get_feedback("req-999")
    assert result is None


def test_list_feedback_pagination(feedback_service, mock_table):
    """Test listing feedback with pagination."""
    mock_table.scan.return_value = {
        "Items": [
            {"request_id": "req-1", "query": "Test1"},
            {"request_id": "req-2", "query": "Test2"},
        ],
        "LastEvaluatedKey": {"request_id": "req-2", "timestamp": 123},
    }

    result = feedback_service.list_feedback(limit=10)
    assert len(result["items"]) == 2
    assert result["last_evaluated_key"] is not None


def test_get_analytics_with_ratings(feedback_service, mock_table):
    """Test analytics calculation with ratings."""
    mock_table.scan.return_value = {
        "Items": [
            {"request_id": "req-1", "rating": 5},
            {"request_id": "req-2", "rating": 4},
            {"request_id": "req-3", "rating": 5},
        ]
    }

    result = feedback_service.get_analytics(days_back=30)
    assert result["total_feedback"] == 3
    assert result["avg_rating"] == pytest.approx(4.67, 0.01)
    assert result["rating_distribution"]["5"] == 2
    assert result["rating_distribution"]["4"] == 1


def test_get_analytics_no_data(feedback_service, mock_table):
    """Test analytics with no feedback."""
    mock_table.scan.return_value = {"Items": []}

    result = feedback_service.get_analytics(days_back=30)
    assert result["total_feedback"] == 0
    assert result["avg_rating"] is None
    assert result["rating_distribution"] == {}
