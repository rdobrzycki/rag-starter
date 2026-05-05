"""Unit tests for text chunking logic."""

from shared.chunking import chunk_text, count_tokens


def test_chunk_text_basic():
    """Test basic chunking functionality."""
    text = "This is a test. " * 500
    chunks = chunk_text(text, max_chars=100, overlap=20)
    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_chunk_text_with_overlap():
    """Test that overlap works correctly."""
    text = "ABCDEFGHIJ" * 50
    chunks = chunk_text(text, max_chars=100, overlap=10)
    assert len(chunks) > 1


def test_chunk_text_short_text():
    """Test chunking with text shorter than chunk size."""
    text = "Short text"
    chunks = chunk_text(text, max_chars=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty():
    """Test chunking empty text returns empty list."""
    chunks = chunk_text("", max_chars=100, overlap=10)
    assert chunks == []


def test_chunk_text_whitespace_normalization():
    """Test that whitespace is normalized."""
    text = "Word1   Word2\n\nWord3\t\tWord4"
    chunks = chunk_text(text, max_chars=100, overlap=10)
    assert len(chunks) == 1
    assert "   " not in chunks[0]
    assert "\n\n" not in chunks[0]


def test_chunk_text_default_params():
    """Test chunking with default parameters."""
    text = "A" * 5000
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 3500 for chunk in chunks)


def test_chunk_text_no_overlap():
    """Test chunking without overlap."""
    text = "A" * 1000
    chunks = chunk_text(text, max_chars=250, overlap=0)
    assert len(chunks) == 4


def test_count_tokens_estimator():
    assert count_tokens("Hello, world!") >= 3


def test_chunk_text_token_strategy_basic():
    text = "This is a sentence. " * 400
    chunks = chunk_text(text, strategy="token", target_tokens=64, overlap_tokens=12)

    assert len(chunks) > 1
    assert all(count_tokens(chunk) <= 80 for chunk in chunks)


def test_chunk_text_token_strategy_short_text():
    text = "Short token text."
    chunks = chunk_text(text, strategy="token", target_tokens=64, overlap_tokens=10)
    assert chunks == [text]
