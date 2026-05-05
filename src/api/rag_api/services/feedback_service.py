"""Feedback storage and retrieval service using DynamoDB."""

import logging
from datetime import datetime, timedelta
from typing import Optional
from mypy_boto3_dynamodb.service_resource import Table
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)


class FeedbackService:
    """Handle feedback persistence and analytics."""

    def __init__(self, table: Table, ttl_days: int = 90):
        self.table = table
        self.ttl_days = ttl_days

    def save_feedback(
        self,
        request_id: str,
        query: str,
        answer: str,
        rating: Optional[int] = None,
        notes: Optional[str] = None,
        expected: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> str:
        """Save feedback to DynamoDB.

        Args:
            request_id: Correlation ID from query request
            query: The question asked
            answer: The answer provided
            rating: User rating (1-5)
            notes: User notes/comments
            expected: What user expected
            trace_id: Alternative trace ID

        Returns:
            feedback_id (same as request_id)
        """
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        ttl_timestamp = int((datetime.utcnow() + timedelta(days=self.ttl_days)).timestamp())

        item = {
            "request_id": request_id,
            "timestamp": timestamp,
            "query": query,
            "answer": answer,
            "ttl": ttl_timestamp,
        }

        if rating is not None:
            item["rating"] = rating
        if notes is not None:
            item["notes"] = notes
        if expected is not None:
            item["expected"] = expected
        if trace_id is not None:
            item["trace_id"] = trace_id

        try:
            self.table.put_item(Item=item)
            logger.info(
                "Feedback saved",
                extra={
                    "request_id": request_id,
                    "rating": rating,
                    "timestamp": timestamp,
                },
            )
            return request_id
        except Exception as e:
            logger.error(
                "Failed to save feedback",
                extra={"request_id": request_id, "error": str(e)},
            )
            raise

    def get_feedback(self, request_id: str) -> Optional[dict]:
        """Retrieve feedback by request_id.

        Args:
            request_id: Correlation ID

        Returns:
            Feedback dict or None if not found
        """
        try:
            response = self.table.query(KeyConditionExpression=Key("request_id").eq(request_id))
            items = response.get("Items", [])
            return items[0] if items else None
        except Exception as e:
            logger.error(
                "Failed to retrieve feedback",
                extra={"request_id": request_id, "error": str(e)},
            )
            return None

    def list_feedback(self, limit: int = 100, start_key: Optional[dict] = None) -> dict:
        """List all feedback with pagination.

        Args:
            limit: Max items to return
            start_key: Pagination token

        Returns:
            {"items": [...], "last_evaluated_key": {...}}
        """
        try:
            kwargs = {"Limit": min(limit, 100)}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key

            response = self.table.scan(**kwargs)
            return {
                "items": response.get("Items", []),
                "last_evaluated_key": response.get("LastEvaluatedKey"),
            }
        except Exception as e:
            logger.error("Failed to list feedback", extra={"error": str(e)})
            return {"items": [], "last_evaluated_key": None}

    def get_analytics(self, days_back: int = 30) -> dict:
        """Get feedback analytics (rating distribution, trends).

        Args:
            days_back: Analyze last N days

        Returns:
            Analytics dict with rating stats
        """
        try:
            cutoff_time = int((datetime.utcnow() - timedelta(days=days_back)).timestamp() * 1000)

            response = self.table.scan(
                FilterExpression=Attr("timestamp").gte(cutoff_time) & Attr("rating").exists()
            )

            items = response.get("Items", [])
            if not items:
                return {
                    "total_feedback": 0,
                    "avg_rating": None,
                    "rating_distribution": {},
                }

            ratings = [item["rating"] for item in items if "rating" in item]
            distribution = {}
            for rating in ratings:
                distribution[str(rating)] = distribution.get(str(rating), 0) + 1

            return {
                "total_feedback": len(items),
                "avg_rating": sum(ratings) / len(ratings) if ratings else None,
                "rating_distribution": distribution,
                "period_days": days_back,
            }
        except Exception as e:
            logger.error("Failed to compute analytics", extra={"error": str(e)})
            return {
                "total_feedback": 0,
                "avg_rating": None,
                "rating_distribution": {},
            }
