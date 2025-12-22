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
    category = getattr(knowledge, 'category', 'other') or 'other'
    language = getattr(knowledge, 'language', 'en') or 'en'
    
    result = await db.execute(
        text("""
            INSERT INTO knowledge_base (source_type, category, title, content, language, embedding, tags, metadata)
            VALUES (:source_type, :category, :title, :content, :language, :embedding, :tags, :metadata)
            RETURNING id, source_type, category, title, content, language, tags, created_at
        """),
        {
            "source_type": knowledge.source_type,
            "category": category,
            "title": knowledge.title,
            "content": knowledge.content,
            "language": language,
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
        category=row.category or 'other',
        title=row.title,
        content=row.content,
        language=row.language or 'en',
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
                SELECT id, source_type, category, title, content, language, tags, created_at
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
                SELECT id, source_type, category, title, content, language, tags, created_at
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
            category=row.category or 'other',
            title=row.title,
            content=row.content,
            language=row.language or 'en',
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
            SELECT id, source_type, category, title, content, language, tags, created_at
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
        category=row.category or 'other',
        title=row.title,
        content=row.content,
        language=row.language or 'en',
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
    """
    Save a chat session as a knowledge base entry (snapshot).
    Each save creates a new entry with the current conversation state.
    """
    # Get session info
    session_result = await db.execute(
        text("SELECT id, title FROM chat_sessions WHERE id = :session_id"),
        {"session_id": request.session_id}
    )
    session = session_result.fetchone()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Get all chat messages
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
    
    # Format chat content
    content_parts = []
    for msg in messages:
        role_label = "User" if msg.role == "user" else "Assistant"
        content_parts.append(f"**{role_label}**: {msg.content}")
    
    full_content = "\n\n".join(content_parts)
    title = request.title or session.title or "Saved Chat"
    
    # Generate embedding
    embedding = generate_embedding(full_content)
    
    # Create knowledge entry (simple snapshot, no sync)
    result = await db.execute(
        text("""
            INSERT INTO knowledge_base (source_type, category, title, content, language, embedding, tags, 
                                        chat_session_id, metadata)
            VALUES ('chat', 'chat-saved', :title, :content, 'en', :embedding, :tags,
                    :session_id, :metadata)
            RETURNING id, source_type, category, title, content, language, tags, created_at
        """),
        {
            "title": title,
            "content": full_content,
            "embedding": str(embedding),
            "tags": request.tags or ['chat-saved'],
            "session_id": request.session_id,
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
                "tags": request.tags or ['chat-saved']
            }
        }]
    )
    
    return KnowledgeResponse(
        id=row.id,
        source_type=row.source_type,
        category=row.category or 'chat-saved',
        title=row.title,
        content=row.content,
        language=row.language or 'en',
        tags=row.tags or [],
        created_at=row.created_at
    )


@router.get("/knowledge/sync-status/{session_id}")
async def get_sync_status(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get the knowledge sync status for a chat session."""
    result = await db.execute(
        text("""
            SELECT knowledge_sync_enabled, synced_knowledge_id, last_synced_message_id
            FROM chat_sessions WHERE id = :session_id
        """),
        {"session_id": session_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    return {
        "sync_enabled": row.knowledge_sync_enabled or False,
        "knowledge_id": row.synced_knowledge_id,
        "last_synced_message_id": row.last_synced_message_id
    }


@router.post("/knowledge/toggle-sync/{session_id}")
async def toggle_sync(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Toggle knowledge sync for a chat session."""
    result = await db.execute(
        text("""
            SELECT knowledge_sync_enabled, synced_knowledge_id
            FROM chat_sessions WHERE id = :session_id
        """),
        {"session_id": session_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    new_status = not (row.knowledge_sync_enabled or False)
    
    await db.execute(
        text("""
            UPDATE chat_sessions 
            SET knowledge_sync_enabled = :enabled, updated_at = NOW()
            WHERE id = :session_id
        """),
        {"enabled": new_status, "session_id": session_id}
    )
    await db.commit()
    
    return {
        "sync_enabled": new_status,
        "knowledge_id": row.synced_knowledge_id,
        "message": f"Sync {'enabled' if new_status else 'disabled'}"
    }


@router.post("/knowledge/from-message")
async def save_message_as_knowledge(
    session_id: UUID,
    message_content: str,
    title: str = None,
    tags: List[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Save a single AI response to knowledge, linked to its chat session.
    """
    # Generate embedding
    embedding = generate_embedding(message_content)
    
    # Save to database with session link
    result = await db.execute(
        text("""
            INSERT INTO knowledge_base (source_type, category, title, content, language, embedding, tags, 
                                        chat_session_id, is_synced_session, metadata)
            VALUES ('chat', 'ai-response', :title, :content, 'en', :embedding, :tags,
                    :session_id, FALSE, :metadata)
            RETURNING id, source_type, category, title, content, language, tags, created_at
        """),
        {
            "title": title or f"AI Response - {str(session_id)[:8]}",
            "content": message_content,
            "embedding": str(embedding),
            "tags": tags or ['ai-response', 'saved-from-chat'],
            "session_id": session_id,
            "metadata": json.dumps({"source_session_id": str(session_id), "type": "single_message"})
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
                "title": row.title,
                "content": message_content[:500],
                "tags": tags or ['ai-response']
            }
        }]
    )
    
    return KnowledgeResponse(
        id=row.id,
        source_type=row.source_type,
        category=row.category or 'ai-response',
        title=row.title,
        content=row.content,
        language=row.language or 'en',
        tags=row.tags or [],
        created_at=row.created_at
    )

