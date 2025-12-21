"""RAG (Retrieval-Augmented Generation) service."""
from typing import List, Dict, Any, Optional
from app.services.embeddings import generate_embedding
from app.database.qdrant_client import get_vector_manager
from app.database.neo4j_client import get_graph_manager
from app.database.postgres import AsyncSessionLocal
from app.config import settings
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class RAGService:
    """Service for retrieval-augmented generation."""
    
    def __init__(self):
        self.top_k = settings.RAG_TOP_K
        self.threshold = settings.RAG_SIMILARITY_THRESHOLD
    
    async def retrieve_context(self, query: str, 
                               include_chapters: bool = True,
                               include_knowledge: bool = True,
                               include_ideas: bool = True,
                               include_graph: bool = True,
                               chapter_filter: int = None) -> Dict[str, Any]:
        """Retrieve relevant context for a query."""
        context = {}
        query_embedding = generate_embedding(query)
        
        # Search vector databases
        vector_manager = get_vector_manager()
        
        if include_chapters:
            chapter_results = vector_manager.search(
                collection="chapters",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            context["chapters"] = [r["payload"] for r in chapter_results]
        
        if include_knowledge:
            knowledge_results = vector_manager.search(
                collection="knowledge",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            context["knowledge"] = [r["payload"] for r in knowledge_results]
        
        if include_ideas:
            idea_results = vector_manager.search(
                collection="ideas",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            context["ideas"] = [r["payload"] for r in idea_results]
        
        # Search graph database for characters, relationships, events
        if include_graph:
            try:
                graph_manager = await get_graph_manager()
                graph_results = await graph_manager.search_graph(query)
                context["graph"] = graph_results
                
                # Extract character names for detailed lookup
                character_names = [c.get("name") for c in graph_results.get("characters", [])]
                if character_names:
                    graph_context = await graph_manager.get_context_for_response(
                        characters=character_names[:3],  # Limit to top 3
                        chapter=chapter_filter
                    )
                    context["characters"] = graph_context.get("characters", [])
                    context["events"] = graph_context.get("events", [])
                    context["locations"] = graph_context.get("locations", [])
            except Exception as e:
                logger.warning(f"Graph search failed: {e}")
        
        return context
    
    async def retrieve_chapters(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """Retrieve relevant chapters."""
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        results = vector_manager.search(
            collection="chapters",
            query_vector=query_embedding,
            limit=limit or self.top_k,
            score_threshold=self.threshold
        )
        
        return [{"score": r["score"], **r["payload"]} for r in results]
    
    async def retrieve_knowledge(self, query: str, 
                                 source_type: str = None,
                                 limit: int = None) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge base entries."""
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        filter_conditions = {}
        if source_type:
            filter_conditions["source_type"] = source_type
        
        results = vector_manager.search(
            collection="knowledge",
            query_vector=query_embedding,
            limit=limit or self.top_k,
            score_threshold=self.threshold,
            filter_conditions=filter_conditions if filter_conditions else None
        )
        
        return [{"score": r["score"], **r["payload"]} for r in results]
    
    async def hybrid_search(self, query: str, 
                           collections: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Perform hybrid search across multiple collections."""
        if collections is None:
            collections = ["chapters", "knowledge", "ideas"]
        
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        results = {}
        for collection in collections:
            search_results = vector_manager.search(
                collection=collection,
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            results[collection] = [{"score": r["score"], **r["payload"]} for r in search_results]
        
        return results
    
    async def search_by_chapter_range(self, query: str, 
                                      start_chapter: int, 
                                      end_chapter: int) -> List[Dict[str, Any]]:
        """Search within a specific chapter range."""
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        # Get all chapters in range, then filter by similarity
        results = vector_manager.search(
            collection="chapters",
            query_vector=query_embedding,
            limit=self.top_k * 2,  # Get more and filter
            score_threshold=self.threshold,
            filter_conditions={
                "chapter_number": list(range(start_chapter, end_chapter + 1))
            }
        )
        
        return [{"score": r["score"], **r["payload"]} for r in results]


def get_rag_service() -> RAGService:
    """Get RAG service instance."""
    return RAGService()

