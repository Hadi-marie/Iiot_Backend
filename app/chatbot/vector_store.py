from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .config import settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            prefer_grpc=False,
            timeout=30.0,
        )
    return _client


def recreate_collection(dim: int) -> None:
    client = get_client()
    if collection_exists():
        client.delete_collection(settings.qdrant_collection)
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
    )


def collection_exists() -> bool:
    try:
        get_client().get_collection(settings.qdrant_collection)
        return True
    except Exception:
        return False


def count() -> int:
    try:
        return get_client().count(settings.qdrant_collection, exact=True).count
    except Exception:
        return 0


def upsert(points: list[dict[str, Any]]) -> None:
    """points: [{id, vector, payload}]"""
    client = get_client()
    batch = [
        qm.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=batch)


def search(
    vector: list[float], top_k: int, doc_type: str | None = None
) -> list[dict[str, Any]]:
    client = get_client()
    query_filter = None
    if doc_type:
        query_filter = qm.Filter(
            must=[qm.FieldCondition(key="doc_type", match=qm.MatchValue(value=doc_type))]
        )
    response = client.query_points(
        collection_name=settings.qdrant_collection,
        query=vector,
        limit=top_k,
        query_filter=query_filter,
        with_payload=True,
    )
    results = []
    for hit in response.points:
        payload = hit.payload or {}
        results.append({"score": float(hit.score), **payload})
    return results
