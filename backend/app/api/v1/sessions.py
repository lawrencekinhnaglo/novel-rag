"""Session management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from typing import List
from uuid import UUID
from datetime import datetime

from app.database.postgres import get_db
from app.database.redis_client import get_conversation_cache
from app.api.v1.models import (
    SessionCreate, SessionUpdate, SessionResponse, SessionListResponse
)

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chat session."""
    result = await db.execute(
        text("""
            INSERT INTO chat_sessions (title) 
            VALUES (:title)
            RETURNING id, title, created_at, updated_at
        """),
        {"title": session_data.title}
    )
    await db.commit()
    row = result.fetchone()
    
    return SessionResponse(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        message_count=0
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List all chat sessions."""
    # Get sessions with message counts
    result = await db.execute(
        text("""
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON s.id = m.session_id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
            LIMIT :limit OFFSET :skip
        """),
        {"limit": limit, "skip": skip}
    )
    rows = result.fetchall()
    
    # Get total count
    count_result = await db.execute(text("SELECT COUNT(*) FROM chat_sessions"))
    total = count_result.scalar()
    
    sessions = [
        SessionResponse(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            message_count=row.message_count
        )
        for row in rows
    ]
    
    return SessionListResponse(sessions=sessions, total=total)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chat session."""
    result = await db.execute(
        text("""
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON s.id = m.session_id
            WHERE s.id = :session_id
            GROUP BY s.id
        """),
        {"session_id": session_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionResponse(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        message_count=row.message_count
    )


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    session_data: SessionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a chat session."""
    if session_data.title:
        await db.execute(
            text("""
                UPDATE chat_sessions 
                SET title = :title, updated_at = NOW()
                WHERE id = :session_id
            """),
            {"title": session_data.title, "session_id": session_id}
        )
        await db.commit()
    
    return await get_session(session_id, db)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a chat session and all its messages."""
    # Delete from database
    result = await db.execute(
        text("DELETE FROM chat_sessions WHERE id = :session_id RETURNING id"),
        {"session_id": session_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Clear from cache
    cache = await get_conversation_cache()
    await cache.clear_session(str(session_id))
    
    return {"message": "Session deleted successfully"}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: UUID,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a chat session."""
    # First check cache
    cache = await get_conversation_cache()
    cached_messages = await cache.get_messages(str(session_id), limit)
    
    if cached_messages and len(cached_messages) >= limit:
        return {"messages": cached_messages[-limit:], "source": "cache"}
    
    # Fall back to database
    result = await db.execute(
        text("""
            SELECT id, role, content, metadata, created_at
            FROM chat_messages
            WHERE session_id = :session_id
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :skip
        """),
        {"session_id": session_id, "limit": limit, "skip": skip}
    )
    rows = result.fetchall()
    
    messages = [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "metadata": row.metadata,
            "created_at": row.created_at.isoformat()
        }
        for row in rows
    ]
    
    return {"messages": messages, "source": "database"}

