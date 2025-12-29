"""Research Library API endpoints - External references and research management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
import json

from app.database.postgres import get_db
from app.services.embeddings import generate_embedding
from app.services.llm_service import get_llm_service

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ResearchItemCreate(BaseModel):
    series_id: Optional[int]
    title: str
    source_url: Optional[str]
    source_type: str = "web"
    content: Optional[str]
    category: Optional[str]
    tags: Optional[List[str]]
    chat_session_id: Optional[str]

class ResearchItemUpdate(BaseModel):
    title: Optional[str]
    content: Optional[str]
    summary: Optional[str]
    category: Optional[str]
    tags: Optional[List[str]]
    is_verified: Optional[bool]

class ResearchLinkCreate(BaseModel):
    research_id: int
    link_type: str
    linked_table: str
    linked_id: int
    notes: Optional[str]

class ResearchFromUrlRequest(BaseModel):
    series_id: Optional[int]
    url: str
    category: Optional[str]
    tags: Optional[List[str]]


# ============================================================================
# RESEARCH ITEMS
# ============================================================================

@router.get("/research")
async def list_research(
    series_id: Optional[int] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all research items, optionally filtered by series or category."""
    conditions = []
    params = {}
    
    if series_id:
        conditions.append("series_id = :series_id")
        params["series_id"] = series_id
    if category:
        conditions.append("category = :category")
        params["category"] = category
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    result = await db.execute(
        text(f"""
            SELECT * FROM research_items
            {where_clause}
            ORDER BY created_at DESC
        """),
        params
    )
    items = result.fetchall()
    return [
        {
            "id": r.id,
            "series_id": r.series_id,
            "title": r.title,
            "source_url": r.source_url,
            "source_type": r.source_type,
            "content": r.content[:500] + "..." if r.content and len(r.content) > 500 else r.content,
            "summary": r.summary,
            "category": r.category,
            "tags": r.tags or [],
            "is_verified": r.is_verified,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in items
    ]


@router.get("/research/{research_id}")
async def get_research_item(research_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific research item with full content."""
    result = await db.execute(
        text("SELECT * FROM research_items WHERE id = :id"),
        {"id": research_id}
    )
    item = result.fetchone()
    
    if not item:
        raise HTTPException(status_code=404, detail="Research item not found")
    
    # Get linked elements
    links_result = await db.execute(
        text("SELECT * FROM research_links WHERE research_id = :id"),
        {"id": research_id}
    )
    links = links_result.fetchall()
    
    return {
        "id": item.id,
        "series_id": item.series_id,
        "title": item.title,
        "source_url": item.source_url,
        "source_type": item.source_type,
        "content": item.content,
        "summary": item.summary,
        "category": item.category,
        "tags": item.tags or [],
        "is_verified": item.is_verified,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "links": [
            {
                "id": l.id,
                "link_type": l.link_type,
                "linked_table": l.linked_table,
                "linked_id": l.linked_id,
                "notes": l.notes
            }
            for l in links
        ]
    }


@router.post("/research")
async def create_research_item(
    item: ResearchItemCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new research item."""
    # Generate embedding if content provided
    embedding = None
    if item.content:
        embedding = generate_embedding(item.content)
    
    # Generate summary using LLM if content is long
    summary = None
    if item.content and len(item.content) > 500:
        try:
            llm = get_llm_service()
            summary_response = await llm.generate([
                {"role": "system", "content": "Summarize the following research content in 2-3 sentences."},
                {"role": "user", "content": item.content[:3000]}
            ], temperature=0.3, max_tokens=200)
            summary = summary_response
        except:
            pass
    
    result = await db.execute(
        text("""
            INSERT INTO research_items (series_id, title, source_url, source_type,
                                        content, summary, category, tags, embedding, chat_session_id)
            VALUES (:series_id, :title, :source_url, :source_type,
                    :content, :summary, :category, :tags, :embedding, :chat_session_id)
            RETURNING *
        """),
        {
            "series_id": item.series_id,
            "title": item.title,
            "source_url": item.source_url,
            "source_type": item.source_type,
            "content": item.content,
            "summary": summary,
            "category": item.category,
            "tags": item.tags,
            "embedding": str(embedding) if embedding else None,
            "chat_session_id": item.chat_session_id
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Research item created successfully", "summary": summary}


@router.put("/research/{research_id}")
async def update_research_item(
    research_id: int,
    item: ResearchItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a research item."""
    updates = []
    params = {"research_id": research_id}
    
    for field in ["title", "content", "summary", "category", "tags", "is_verified"]:
        value = getattr(item, field)
        if value is not None:
            updates.append(f"{field} = :{field}")
            params[field] = value
    
    # Regenerate embedding if content changed
    if item.content:
        embedding = generate_embedding(item.content)
        updates.append("embedding = :embedding")
        params["embedding"] = str(embedding)
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    updates.append("updated_at = NOW()")
    
    result = await db.execute(
        text(f"UPDATE research_items SET {', '.join(updates)} WHERE id = :research_id RETURNING *"),
        params
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Research item not found")
    
    return {"message": "Research item updated successfully"}


@router.delete("/research/{research_id}")
async def delete_research_item(research_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a research item."""
    result = await db.execute(
        text("DELETE FROM research_items WHERE id = :id RETURNING id"),
        {"id": research_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Research item not found")
    
    return {"message": "Research item deleted successfully"}


# ============================================================================
# RESEARCH LINKS
# ============================================================================

@router.post("/research/link")
async def create_research_link(
    link: ResearchLinkCreate,
    db: AsyncSession = Depends(get_db)
):
    """Link research to a story element."""
    result = await db.execute(
        text("""
            INSERT INTO research_links (research_id, link_type, linked_table, linked_id, notes)
            VALUES (:research_id, :link_type, :linked_table, :linked_id, :notes)
            RETURNING *
        """),
        {
            "research_id": link.research_id,
            "link_type": link.link_type,
            "linked_table": link.linked_table,
            "linked_id": link.linked_id,
            "notes": link.notes
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Research link created successfully"}


@router.delete("/research/link/{link_id}")
async def delete_research_link(link_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a research link."""
    result = await db.execute(
        text("DELETE FROM research_links WHERE id = :id RETURNING id"),
        {"id": link_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Link not found")
    
    return {"message": "Research link deleted successfully"}


# ============================================================================
# RESEARCH SEARCH
# ============================================================================

@router.get("/research/search")
async def search_research(
    query: str,
    series_id: Optional[int] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Search research items by semantic similarity."""
    query_embedding = generate_embedding(query)
    
    series_filter = "AND series_id = :series_id" if series_id else ""
    params = {"embedding": str(query_embedding), "limit": limit}
    if series_id:
        params["series_id"] = series_id
    
    result = await db.execute(
        text(f"""
            SELECT *, 
                   1 - (embedding <=> :embedding::vector) as similarity
            FROM research_items
            WHERE embedding IS NOT NULL {series_filter}
            ORDER BY embedding <=> :embedding::vector
            LIMIT :limit
        """),
        params
    )
    items = result.fetchall()
    return [
        {
            "id": r.id,
            "title": r.title,
            "summary": r.summary,
            "category": r.category,
            "similarity": round(r.similarity, 3) if r.similarity else None
        }
        for r in items
    ]


# ============================================================================
# CATEGORIES
# ============================================================================

@router.get("/research/categories")
async def get_research_categories(db: AsyncSession = Depends(get_db)):
    """Get all unique research categories."""
    result = await db.execute(
        text("""
            SELECT DISTINCT category, COUNT(*) as count
            FROM research_items
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
    )
    categories = result.fetchall()
    return [{"name": c.category, "count": c.count} for c in categories]

