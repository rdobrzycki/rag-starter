"""Text chunking with sentence-aware splitting for embedding generation."""

from __future__ import annotations

import re
from typing import Literal

ChunkingStrategy = Literal["character", "token"]


def count_tokens(text: str) -> int:
    """Estimate token count for plain text.

    Uses a lightweight regex-based approximation to avoid heavy runtime
    dependencies in Lambda and API containers.
    """
    if not text:
        return 0
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    # Pattern matches sentence endings: . ! ? followed by space or end of string
    # Also handles common abbreviations and decimal numbers
    sentence_endings = r"(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])(?=\s*$)"
    sentences = re.split(sentence_endings, text)
    # Filter out empty sentences
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    *,
    strategy: ChunkingStrategy = "character",
    max_chars: int = 3500,
    overlap: int = 300,
    target_tokens: int = 768,
    overlap_tokens: int = 128,
) -> list[str]:
    """Split text into sentence-aware overlapping chunks for embedding generation.

    This function preserves sentence boundaries when possible, avoiding mid-sentence
    splits which can hurt embedding quality. Falls back to character-based splitting
    if sentences are too long.

    Normalizes whitespace and creates chunks with specified overlap to maintain
    context across chunk boundaries.

    Args:
        text: Text to chunk
        strategy: Chunking strategy ("character" or "token")
        max_chars: Maximum characters per chunk for character strategy (default: 3500)
        overlap: Number of characters to overlap for character strategy (default: 300)
        target_tokens: Target tokens per chunk for token strategy (default: 768)
        overlap_tokens: Overlap tokens for token strategy (default: 128)

    Returns:
        List of text chunks, empty list if input text is empty
    """
    text = " ".join(text.split())
    if not text:
        return []

    if strategy == "token":
        return _chunk_text_token_based(
            text=text,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )

    # Split into sentences
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_chunk: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_length = len(sentence) + 1  # +1 for space

        # If single sentence exceeds max_chars, split it character-based
        if len(sentence) > max_chars:
            # Flush current chunk if any
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_length = 0

            # Split long sentence character-based
            start = 0
            while start < len(sentence):
                end = min(start + max_chars, len(sentence))
                chunk = sentence[start:end].strip()
                if chunk:
                    chunks.append(chunk)
                if end >= len(sentence):
                    break
                start = max(0, end - overlap)
            continue

        # Check if adding this sentence would exceed max_chars
        if current_length + sentence_length > max_chars and current_chunk:
            # Flush current chunk
            chunks.append(" ".join(current_chunk))

            # Start new chunk with overlap from previous chunk
            # Take last sentences that fit in overlap
            overlap_text = " ".join(current_chunk)
            if len(overlap_text) > overlap:
                overlap_sentences = []
                overlap_length = 0
                # Work backwards to find sentences that fit in overlap
                for s in reversed(current_chunk):
                    if overlap_length + len(s) + 1 <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_length += len(s) + 1
                    else:
                        break
                current_chunk = overlap_sentences + [sentence]
                current_length = sum(len(s) + 1 for s in current_chunk) - 1
            else:
                current_chunk = current_chunk + [sentence]
                current_length = sum(len(s) + 1 for s in current_chunk) - 1
        else:
            # Add sentence to current chunk
            current_chunk.append(sentence)
            current_length += sentence_length

    # Add final chunk if any
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _chunk_text_token_based(
    *,
    text: str,
    target_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Split text into sentence-aware overlapping token chunks."""
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)

        # If a sentence is larger than target token budget, split into token windows.
        if sentence_tokens > target_tokens:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            sentence_parts = _split_long_sentence_by_tokens(
                sentence=sentence,
                target_tokens=target_tokens,
                overlap_tokens=overlap_tokens,
            )
            chunks.extend(sentence_parts)
            continue

        if current_chunk and (current_tokens + sentence_tokens > target_tokens):
            chunks.append(" ".join(current_chunk))

            overlap_sentences = _tail_overlap_sentences(
                sentences=current_chunk,
                overlap_tokens=overlap_tokens,
            )
            current_chunk = overlap_sentences + [sentence]
            current_tokens = sum(count_tokens(s) for s in current_chunk)
        else:
            current_chunk.append(sentence)
            current_tokens += sentence_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _split_long_sentence_by_tokens(
    *,
    sentence: str,
    target_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """Split an oversized sentence into token windows."""
    pieces = re.findall(r"\S+", sentence)
    if not pieces:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for piece in pieces:
        piece_tokens = count_tokens(piece)
        if current and (current_tokens + piece_tokens > target_tokens):
            chunks.append(" ".join(current))
            tail = _tail_overlap_sentences(sentences=current, overlap_tokens=overlap_tokens)
            current = tail + [piece]
            current_tokens = sum(count_tokens(p) for p in current)
        else:
            current.append(piece)
            current_tokens += piece_tokens

    if current:
        chunks.append(" ".join(current))

    return chunks


def _tail_overlap_sentences(*, sentences: list[str], overlap_tokens: int) -> list[str]:
    if overlap_tokens <= 0:
        return []

    out: list[str] = []
    running = 0
    for sentence in reversed(sentences):
        tokens = count_tokens(sentence)
        if out and (running + tokens > overlap_tokens):
            break
        out.insert(0, sentence)
        running += tokens
        if running >= overlap_tokens:
            break
    return out
