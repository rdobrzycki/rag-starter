"""Context building for LLM prompts."""

from __future__ import annotations

from typing import Iterable

from .retrieval import Retrieved


def build_context(
    chunks: Iterable[Retrieved],
    *,
    max_chunks: int = 8,
    max_chars_per_chunk: int = 1600,
) -> str:
    """Build a compact, citeable context block for the LLM.

    Formats retrieved chunks with metadata (chunk_id, score, source_uri)
    and truncates long chunks to fit within token limits.

    Args:
        chunks: Iterable of Retrieved chunks
        max_chunks: Maximum number of chunks to include
        max_chars_per_chunk: Maximum characters per chunk before truncation

    Returns:
        Formatted context string with chunk metadata and text
    """
    parts: list[str] = []
    for c in list(chunks)[:max_chunks]:
        text = (c.text or "").strip()
        if len(text) > max_chars_per_chunk:
            text = text[:max_chars_per_chunk].rstrip() + "…"

        parts.append(
            "\n".join(
                [
                    f"[chunk_id={c.chunk_id} score={c.score:.3f} source={c.source_uri}]",
                    text,
                ]
            )
        )
    return "\n\n---\n\n".join(parts)
