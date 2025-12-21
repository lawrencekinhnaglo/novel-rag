"""Knowledge base API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List
from uuid import UUID
import json

from app.database.postgres import get_db
from app.database.qdrant_client import get_vector_manager
from app.services.embeddings import generate_embedding
from app.api.v1.models import (
    KnowledgeCreate, KnowledgeResponse, SaveChatAsKnowledge
)

router = APIRouter()


@router.post("/knowledge", response_model=KnowledgeResponse)
async def create_knowledge(
    knowledge: KnowledgeCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new knowledge base entry."""
    # Generate embedding
    embedding = generate_embedding(knowledge.content)
    
    # Save to PostgreSQL
    result = await db.execute(
        text("""
            INSERT INTO knowledge_base (source_type, title, content, embedding, tags, metadata)
            VALUES (:source_type, :title, :content, :embedding, :tags, :metadata)
            RETURNING id, source_type, title, content, tags, created_at
        """),
        {
            "source_type": knowledge.source_type,
            "title": knowledge.title,
            "content": knowledge.content,
            "embedding": str(embedding),
            "tags": knowledge.tags,
            "metadata": json.dumps(knowledge.metadata)
        }
    )
    await db.commit()
    row = result.fetchone()
    
    # Save to Qdrant
    vector_manager = get_vector_manager()
    vector_manager.upsert_vectors(
        collection="knowledge",
        points=[{
            "id": row.id,
            "vector": embedding,
            "payload": {
                "id": row.id,
                "source_type": knowledge.source_type,
                "title": knowledge.title,
                "content": knowledge.content[:500],  # Store truncated for payload
                "tags": knowledge.tags
            }
        }]
    )
    
    return KnowledgeResponse(
        id=row.id,
        source_type=row.source_type,
        title=row.title,
        content=row.content,
        tags=row.tags or [],
        created_at=row.created_at
    )


@router.get("/knowledge", response_model=List[KnowledgeResponse])
async def list_knowledge(
    source_type: str = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List knowledge base entries."""
    if source_type:
        result = await db.execute(
            text("""
                SELECT id, source_type, title, content, tags, created_at
                FROM knowledge_base
                WHERE source_type = :source_type
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :skip
            """),
            {"source_type": source_type, "limit": limit, "skip": skip}
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, source_type, title, content, tags, created_at
                FROM knowledge_base
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :skip
            """),
            {"limit": limit, "skip": skip}
        )
    
    rows = result.fetchall()
    return [
        KnowledgeResponse(
            id=row.id,
            source_type=row.source_type,
            title=row.title,
            content=row.content,
            tags=row.tags or [],
            created_at=row.created_at
        )
        for row in rows
    ]


@router.get("/knowledge/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific knowledge base entry."""
    result = await db.execute(
        text("""
            SELECT id, source_type, title, content, tags, created_at
            FROM knowledge_base
            WHERE id = :knowledge_id
        """),
        {"knowledge_id": knowledge_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    return KnowledgeResponse(
        id=row.id,
        source_type=row.source_type,
        title=row.title,
        content=row.content,
        tags=row.tags or [],
        created_at=row.created_at
    )


@router.delete("/knowledge/{knowledge_id}")
async def delete_knowledge(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a knowledge base entry."""
    result = await db.execute(
        text("DELETE FROM knowledge_base WHERE id = :knowledge_id RETURNING id"),
        {"knowledge_id": knowledge_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Delete from Qdrant
    vector_manager = get_vector_manager()
    vector_manager.delete_vectors("knowledge", [str(knowledge_id)])
    
    return {"message": "Knowledge entry deleted successfully"}


@router.post("/knowledge/from-chat")
async def save_chat_as_knowledge(
    request: SaveChatAsKnowledge,
    db: AsyncSession = Depends(get_db)
):
    """Save a chat session as a knowledge base entry."""
    # Get chat messages
    result = await db.execute(
        text("""
            SELECT role, content, created_at
            FROM chat_messages
            WHERE session_id = :session_id
            ORDER BY created_at ASC
        """),
        {"session_id": request.session_id}
    )
    messages = result.fetchall()
    
    if not messages:
        raise HTTPException(status_code=404, detail="No messages found in session")
    
    # Get session title
    session_result = await db.execute(
        text("SELECT title FROM chat_sessions WHERE id = :session_id"),
        {"session_id": request.session_id}
    )
    session = session_result.fetchone()
    
    # Format chat content
    content_parts = []
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Assistant"
        content_parts.append(f"**{role_label}**: {msg.content}")
    
    full_content = "\n\n".join(content_parts)
    title = request.title or session.title if session else "Saved Chat"
    
    # Generate embedding
    embedding = generate_embedding(full_content)
    
    # Save to database
    result = await db.execute(
        text("""
            INSERT INTO knowledge_base (source_type, title, content, embedding, tags, metadata)
            VALUES ('chat', :title, :content, :embedding, :tags, :metadata)
            RETURNING id, source_type, title, content, tags, created_at
        """),
        {
            "title": title,
            "content": full_content,
            "embedding": str(embedding),
            "tags": request.tags,
            "metadata": json.dumps({"source_session_id": str(request.session_id)})
        }
    )
    await db.commit()
    row = result.fetchone()
    
    # Save to Qdrant
    vector_manager = get_vector_manager()
    vector_manager.upsert_vectors(
        collection="knowledge",
        points=[{
            "id": row.id,
            "vector": embedding,
            "payload": {
                "id": row.id,
                "source_type": "chat",
                "title": title,
                "content": full_content[:500],
                "tags": request.tags
            }
        }]
    )
    
    return KnowledgeResponse(
        id=row.id,
        source_type=row.source_type,
        title=row.title,
        content=row.content,
        tags=row.tags or [],
        created_at=row.created_at
    )

