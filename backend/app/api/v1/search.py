"""Search API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.database.postgres import get_db
from app.services.rag_service import get_rag_service
from app.services.web_search import get_web_search_service
from app.api.v1.models import SearchRequest, SearchResponse, WebSearchRequest, WebSearchResponse

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """Search across all content using RAG."""
    rag_service = get_rag_service()
    
    results = await rag_service.hybrid_search(
        query=request.query,
        collections=request.collections
    )
    
    # Include graph search if requested
    if request.include_graph:
        from app.database.neo4j_client import get_graph_manager
        graph_manager = await get_graph_manager()
        graph_results = await graph_manager.search_graph(request.query)
        results["graph"] = graph_results
    
    # Count total results
    total = sum(len(v) if isinstance(v, list) else 0 for v in results.values())
    
    return SearchResponse(
        query=request.query,
        results=results,
        total_results=total
    )


@router.post("/search/chapters")
async def search_chapters(
    query: str,
    start_chapter: int = None,
    end_chapter: int = None,
    limit: int = 5
):
    """Search within chapters."""
    rag_service = get_rag_service()
    
    if start_chapter is not None and end_chapter is not None:
        results = await rag_service.search_by_chapter_range(
            query=query,
            start_chapter=start_chapter,
            end_chapter=end_chapter
        )
    else:
        results = await rag_service.retrieve_chapters(query, limit)
    
    return {"query": query, "results": results}


@router.post("/search/knowledge")
async def search_knowledge(
    query: str,
    source_type: str = None,
    limit: int = 5
):
    """Search knowledge base."""
    rag_service = get_rag_service()
    results = await rag_service.retrieve_knowledge(
        query=query,
        source_type=source_type,
        limit=limit
    )
    return {"query": query, "results": results}


@router.post("/search/web", response_model=WebSearchResponse)
async def web_search(request: WebSearchRequest):
    """Perform a web search."""
    search_service = get_web_search_service()
    
    if request.search_type == "news":
        results = search_service.search_news(request.query, request.max_results)
    elif request.search_type == "images":
        results = search_service.search_images(request.query, request.max_results)
    else:
        results = search_service.search(request.query, request.max_results)
    
    return WebSearchResponse(
        query=request.query,
        results=results,
        search_type=request.search_type
    )


@router.get("/search/similar/{content_type}/{content_id}")
async def find_similar(
    content_type: str,
    content_id: int,
    limit: int = 5,
    db: AsyncSession = Depends(get_db)
):
    """Find similar content based on an existing piece of content."""
    from sqlalchemy import text
    from app.services.embeddings import generate_embedding
    from app.database.qdrant_client import get_vector_manager
    
    # Get the content based on type
    if content_type == "chapter":
        result = await db.execute(
            text("SELECT content FROM chapters WHERE id = :id"),
            {"id": content_id}
        )
    elif content_type == "knowledge":
        result = await db.execute(
            text("SELECT content FROM knowledge_base WHERE id = :id"),
            {"id": content_id}
        )
    elif content_type == "idea":
        result = await db.execute(
            text("SELECT content FROM ideas WHERE id = :id"),
            {"id": content_id}
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid content type")
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Content not found")
    
    # Generate embedding and search
    embedding = generate_embedding(row.content)
    vector_manager = get_vector_manager()
    
    # Search in the same collection, excluding the source
    collection_map = {
        "chapter": "chapters",
        "knowledge": "knowledge",
        "idea": "ideas"
    }
    
    results = vector_manager.search(
        collection=collection_map[content_type],
        query_vector=embedding,
        limit=limit + 1,  # Get one extra to filter out source
        score_threshold=0.3  # Wider threshold for general search
    )
    
    # Filter out the source content
    filtered_results = [
        {"score": r["score"], **r["payload"]}
        for r in results
        if r["payload"].get("id") != content_id
    ][:limit]
    
    return {
        "source_id": content_id,
        "source_type": content_type,
        "similar_content": filtered_results
    }

