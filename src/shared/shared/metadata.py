"""Standardized metadata schema for vector points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ChunkMetadata:
    """Standardized metadata for a vector chunk.

    Required fields ensure consistency across ingestion paths and enable
    proper filtering, citation, and deduplication.
    """

    # Required fields
    doc_id: str
    chunk_index: int
    source_uri: str
    text: str
    hash: str
    created_at: str

    # Optional fields for enhanced retrieval and citation
    doc_name: str | None = None
    page_number: int | None = None
    section: str | None = None
    document_type: str | None = None

    def to_payload(self, additional_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Convert metadata to Qdrant payload format.

        Args:
            additional_metadata: Optional additional metadata to merge in

        Returns:
            Dictionary suitable for Qdrant point payload
        """
        payload: dict[str, Any] = {
            "doc_id": self.doc_id,
            "chunk_index": self.chunk_index,
            "source_uri": self.source_uri,
            "text": self.text,
            "hash": self.hash,
            "created_at": self.created_at,
        }

        # Add optional fields if present
        if self.doc_name:
            payload["doc_name"] = self.doc_name
        if self.page_number is not None:
            payload["page_number"] = self.page_number
        if self.section:
            payload["section"] = self.section
        if self.document_type:
            payload["document_type"] = self.document_type

        # Merge additional metadata
        if additional_metadata:
            payload.update(additional_metadata)

        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ChunkMetadata:
        """Create ChunkMetadata from Qdrant payload.

        Args:
            payload: Qdrant point payload dictionary

        Returns:
            ChunkMetadata instance
        """
        return cls(
            doc_id=payload.get("doc_id", ""),
            chunk_index=payload.get("chunk_index", 0),
            source_uri=payload.get("source_uri", ""),
            text=payload.get("text", ""),
            hash=payload.get("hash", ""),
            created_at=payload.get("created_at", ""),
            doc_name=payload.get("doc_name"),
            page_number=payload.get("page_number"),
            section=payload.get("section"),
            document_type=payload.get("document_type"),
        )
