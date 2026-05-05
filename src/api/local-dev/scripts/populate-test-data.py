#!/usr/bin/env python3
"""Populate Qdrant with test data for local API development."""

import sys
import random
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct


def populate_test_data():
    """Insert sample documents into Qdrant for local testing."""
    client = QdrantClient(url="http://localhost:6333")
    collection = "documents"

    # Ensure collection exists
    try:
        client.get_collection(collection)
        print(f"Collection '{collection}' exists")
    except Exception:
        print(f"Creating collection '{collection}'...")
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )

    # Sample test documents
    test_docs = [
        {
            "text": "The company privacy policy requires all data to be encrypted at rest and in transit. All employees must follow data handling procedures.",
            "source": "s3://test-bucket/privacy-policy.pdf",
            "doc_id": "doc-001",
        },
        {
            "text": "Employee handbook states that remote work is allowed up to 3 days per week. Office hours are 9 AM to 5 PM.",
            "source": "s3://test-bucket/employee-handbook.pdf",
            "doc_id": "doc-002",
        },
        {
            "text": "Data retention policy requires personal data to be deleted after 7 years. Financial records must be kept for 10 years.",
            "source": "s3://test-bucket/data-retention.pdf",
            "doc_id": "doc-003",
        },
        {
            "text": "Security guidelines mandate multi-factor authentication for all systems. Passwords must be changed every 90 days.",
            "source": "s3://test-bucket/security-guidelines.pdf",
            "doc_id": "doc-004",
        },
    ]

    # Generate random vectors (NOTE: In production, use real Bedrock embeddings)
    points = []
    for idx, doc in enumerate(test_docs):
        # Random vectors for testing - not semantically meaningful
        vector = [random.random() for _ in range(1024)]

        points.append(
            PointStruct(
                id=idx,
                vector=vector,
                payload={
                    "text": doc["text"],
                    "source_uri": doc["source"],
                    "doc_id": doc["doc_id"],
                    "chunk_index": 0,
                },
            )
        )

    client.upsert(collection_name=collection, points=points)
    print(f"✓ Inserted {len(points)} test documents")
    print("\nTest with: task local:api:query QUERY='What is the privacy policy?'")


if __name__ == "__main__":
    try:
        populate_test_data()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
