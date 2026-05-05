"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError
from rag_api.models import (
    QueryRequest,
    ChunkingConfig,
    DocumentIngestRequest,
    CollectionCreateRequest,
    EmbedRequest,
    FeedbackRequest,
)


class TestQueryRequest:
    """Tests for QueryRequest model."""

    def test_query_request_basic(self):
        """Test basic query request validation."""
        req = QueryRequest(query="What is AI?")
        assert req.query == "What is AI?"
        assert req.top_k is None
        assert req.filters is None
        assert req.min_score is None
        assert req.return_context is False
        assert req.collection is None

    def test_query_request_with_all_fields(self):
        """Test query request with all fields."""
        req = QueryRequest(
            query="test",
            top_k=10,
            filters={"must": [{"key": "category", "match": {"value": "tech"}}]},
            min_score=0.8,
            return_context=True,
            collection="custom-docs",
        )
        assert req.top_k == 10
        assert req.min_score == 0.8
        assert req.return_context is True

    def test_query_request_validation_empty_query(self):
        """Test that empty query is rejected."""
        with pytest.raises(ValidationError):
            QueryRequest(query="")

    def test_query_request_validation_top_k_range(self):
        """Test top_k validation."""
        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=0)

        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=21)

    def test_query_request_validation_min_score_range(self):
        """Test min_score validation."""
        with pytest.raises(ValidationError):
            QueryRequest(query="test", min_score=-0.1)

        with pytest.raises(ValidationError):
            QueryRequest(query="test", min_score=1.1)


class TestChunkingConfig:
    """Tests for ChunkingConfig model."""

    def test_chunking_config_defaults(self):
        """Test default chunking configuration."""
        config = ChunkingConfig()
        assert config.strategy == "character"
        assert config.chunk_size == 3500
        assert config.overlap == 300
        assert config.target_tokens == 768
        assert config.overlap_tokens == 128

    def test_chunking_config_custom(self):
        """Test custom chunking configuration."""
        config = ChunkingConfig(
            strategy="token",
            chunk_size=2000,
            overlap=200,
            target_tokens=1024,
            overlap_tokens=128,
        )
        assert config.strategy == "token"
        assert config.chunk_size == 2000
        assert config.overlap == 200
        assert config.target_tokens == 1024
        assert config.overlap_tokens == 128

    def test_chunking_config_validation_chunk_size(self):
        """Test chunk_size validation."""
        with pytest.raises(ValidationError):
            ChunkingConfig(chunk_size=50)

        with pytest.raises(ValidationError):
            ChunkingConfig(chunk_size=11000)

    def test_chunking_config_validation_overlap(self):
        """Test overlap validation."""
        with pytest.raises(ValidationError):
            ChunkingConfig(overlap=-1)

        with pytest.raises(ValidationError):
            ChunkingConfig(overlap=1500)

    def test_chunking_config_validation_token_bounds(self):
        with pytest.raises(ValidationError):
            ChunkingConfig(target_tokens=50)

        with pytest.raises(ValidationError):
            ChunkingConfig(target_tokens=3000)

        with pytest.raises(ValidationError):
            ChunkingConfig(overlap_tokens=-1)

        with pytest.raises(ValidationError):
            ChunkingConfig(overlap_tokens=600)


class TestDocumentIngestRequest:
    """Tests for DocumentIngestRequest model."""

    def test_document_ingest_basic(self):
        """Test basic document ingest request."""
        req = DocumentIngestRequest(source_uri="test://doc.pdf", text="Sample text")
        assert req.source_uri == "test://doc.pdf"
        assert req.text == "Sample text"
        assert req.metadata == {}
        assert req.collection is None

    def test_document_ingest_with_metadata(self):
        """Test document ingest with metadata."""
        req = DocumentIngestRequest(
            source_uri="test://doc.pdf",
            text="Sample text",
            metadata={"author": "John", "year": 2024},
        )
        assert req.metadata["author"] == "John"

    def test_document_ingest_validation_empty_text(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValidationError):
            DocumentIngestRequest(source_uri="test://doc.pdf", text="")


class TestCollectionCreateRequest:
    """Tests for CollectionCreateRequest model."""

    def test_collection_create_basic(self):
        """Test basic collection creation request."""
        req = CollectionCreateRequest(name="test-collection")
        assert req.name == "test-collection"
        assert req.vector_size == 1024
        assert req.distance == "Cosine"

    def test_collection_create_validation_invalid_name(self):
        """Test collection name validation."""
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="invalid name")

        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="invalid@name")

    def test_collection_create_validation_vector_size(self):
        """Test vector size validation."""
        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="test", vector_size=100)

        with pytest.raises(ValidationError):
            CollectionCreateRequest(name="test", vector_size=5000)


class TestEmbedRequest:
    """Tests for EmbedRequest model."""

    def test_embed_request_basic(self):
        """Test basic embed request."""
        req = EmbedRequest(text="Sample text")
        assert req.text == "Sample text"

    def test_embed_request_validation_empty(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValidationError):
            EmbedRequest(text="")

    def test_embed_request_validation_too_long(self):
        """Test that text exceeding max length is rejected."""
        with pytest.raises(ValidationError):
            EmbedRequest(text="A" * 10001)


class TestFeedbackRequest:
    """Tests for FeedbackRequest model."""

    def test_feedback_request_basic(self):
        """Test basic feedback request."""
        req = FeedbackRequest(query="test query", answer="test answer")
        assert req.query == "test query"
        assert req.answer == "test answer"
        assert req.rating is None

    def test_feedback_request_with_rating(self):
        """Test feedback request with rating."""
        req = FeedbackRequest(query="test", answer="test", rating=5)
        assert req.rating == 5

    def test_feedback_request_validation_invalid_rating(self):
        """Test rating validation."""
        with pytest.raises(ValidationError):
            FeedbackRequest(query="test", answer="test", rating=0)

        with pytest.raises(ValidationError):
            FeedbackRequest(query="test", answer="test", rating=6)
