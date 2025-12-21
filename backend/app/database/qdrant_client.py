"""Qdrant vector database client for semantic search."""
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.config import settings

# Qdrant client instance
qdrant: Optional[QdrantClient] = None

COLLECTIONS = {
    "chapters": "novel_chapters",
    "knowledge": "novel_knowledge",
    "ideas": "novel_ideas",
    "messages": "chat_messages"
}


async def init_qdrant():
    """Initialize Qdrant connection and collections."""
    global qdrant
    qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    
    # Get list of existing collections
    try:
        existing_collections = [c.name for c in qdrant.get_collections().collections]
    except Exception:
        existing_collections = []
    
    # Create collections if they don't exist
    for collection_name in COLLECTIONS.values():
        if collection_name not in existing_collections:
            try:
                qdrant.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=settings.EMBEDDING_DIMENSION,
                        distance=Distance.COSINE
                    )
                )
            except Exception as e:
                # Collection might already exist
                if "already exists" not in str(e):
                    raise


def get_qdrant() -> QdrantClient:
    """Get Qdrant client."""
    if not qdrant:
        raise RuntimeError("Qdrant not initialized")
    return qdrant


class VectorSearchManager:
    """Manager for vector search operations."""
    
    def __init__(self, client: QdrantClient):
        self.client = client
    
    def upsert_vectors(self, collection: str, points: List[Dict[str, Any]]):
        """Insert or update vectors in a collection."""
        collection_name = COLLECTIONS.get(collection, collection)
        point_structs = [
            PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {})
            )
            for p in points
        ]
        self.client.upsert(collection_name=collection_name, points=point_structs)
    
    def search(self, collection: str, query_vector: List[float], 
               limit: int = 5, score_threshold: float = None,
               filter_conditions: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        collection_name = COLLECTIONS.get(collection, collection)
        
        # Build filter if provided
        query_filter = None
        if filter_conditions:
            must_conditions = []
            for key, value in filter_conditions.items():
                if isinstance(value, list):
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=value)
                        )
                    )
                else:
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value)
                        )
                    )
            query_filter = models.Filter(must=must_conditions)
        
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter
        )
        
        return [
            {
                "id": r.id,
                "score": r.score,
                "payload": r.payload
            }
            for r in results
        ]
    
    def delete_vectors(self, collection: str, ids: List[str]):
        """Delete vectors by ID."""
        collection_name = COLLECTIONS.get(collection, collection)
        self.client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=ids)
        )
    
    def get_collection_info(self, collection: str) -> Dict[str, Any]:
        """Get collection information."""
        collection_name = COLLECTIONS.get(collection, collection)
        info = self.client.get_collection(collection_name)
        return {
            "name": collection_name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count
        }


def get_vector_manager() -> VectorSearchManager:
    """Get vector search manager instance."""
    return VectorSearchManager(get_qdrant())

