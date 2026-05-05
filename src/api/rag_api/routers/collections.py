from __future__ import annotations
import logging
from typing import Any
from fastapi import APIRouter, Depends, Path, HTTPException
from qdrant_client.models import VectorParams, Distance
from ..models import (
    CollectionListResponse,
    CollectionCreateRequest,
    CollectionCreateResponse,
    CollectionInfo,
)
from ..dependencies import get_qdrant

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=CollectionListResponse)
def list_collections(qc: Any = Depends(get_qdrant)) -> CollectionListResponse:
    """List all available collections."""
    collections = qc.get_collections()
    names = [c.name for c in collections.collections]
    return CollectionListResponse(collections=names)


@router.post("", response_model=CollectionCreateResponse, status_code=201)
def create_collection(
    req: CollectionCreateRequest, qc: Any = Depends(get_qdrant)
) -> CollectionCreateResponse:
    """Create a new collection with specified vector configuration."""
    try:
        qc.create_collection(
            collection_name=req.name,
            vectors_config=VectorParams(
                size=req.vector_size, distance=Distance[req.distance.upper()]
            ),
        )
        return CollectionCreateResponse(name=req.name, status="created")
    except Exception as e:
        if "already exists" in str(e).lower():
            return CollectionCreateResponse(name=req.name, status="already_exists")
        logger.exception("Failed to create collection: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{name}", response_model=CollectionInfo)
def get_collection_info(
    name: str = Path(..., description="Collection name"), qc: Any = Depends(get_qdrant)
) -> CollectionInfo:
    """Get detailed information about a collection."""
    try:
        info = qc.get_collection(name)
        return CollectionInfo(
            name=name,
            vector_size=info.config.params.vectors.size,
            distance=str(info.config.params.vectors.distance),
            points_count=info.points_count,
            status=str(info.status),
        )
    except Exception as e:
        logger.exception("Failed to get collection info: %s", e)
        raise HTTPException(status_code=404, detail=f"Collection '{name}' not found") from e


@router.delete("/{name}", status_code=204)
def delete_collection(
    name: str = Path(..., description="Collection name"), qc: Any = Depends(get_qdrant)
) -> None:
    """Delete a collection."""
    try:
        qc.delete_collection(name)
    except Exception as e:
        logger.exception("Failed to delete collection: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
