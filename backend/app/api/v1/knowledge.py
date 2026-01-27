"""Knowledge base API endpoints with intelligent entity extraction."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID
import json
import logging

from app.database.postgres import get_db
from app.database.qdrant_client import get_vector_manager
from app.services.embeddings import generate_embedding
from app.services.entity_extraction import get_entity_extraction_service
from app.api.v1.models import (
    KnowledgeCreate, KnowledgeResponse, SaveChatAsKnowledge
)

router = APIRouter()
logger = logging.getLogger(__name__)


def ensure_series_tag(tags: List[str], series_id: Optional[int]) -> List[str]:
    """Ensure tags include series:{id} tag if series_id is provided."""
    if not series_id:
        return tags or []
    series_tag = f"series:{series_id}"
    tag_list = tags or []
    if series_tag not in tag_list:
        return tag_list + [series_tag]
    return tag_list


class IntelligentKnowledgeCreate(BaseModel):
    """Extended knowledge creation with intelligent extraction."""
    title: Optional[str] = None
    content: str
    source_type: str = "manual"
    tags: List[str] = []
    series_id: Optional[int] = None
    language: str = "zh-CN"
    enable_extraction: bool = True  # Enable LLM-powered entity extraction
    metadata: dict = {}


@router.post("/knowledge", response_model=KnowledgeResponse)
async def create_knowledge(
    knowledge: KnowledgeCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new knowledge base entry (basic, without intelligent extraction)."""
    # Generate embedding
    embedding = generate_embedding(knowledge.content)

    # Save to PostgreSQL
    category = getattr(knowledge, 'category', 'other') or 'other'
    language = getattr(knowledge, 'language', 'en') or 'en'

    # Extract series_id from metadata and ensure series tag
    series_id = (knowledge.metadata or {}).get("series_id")
    tags = ensure_series_tag(knowledge.tags, series_id)

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
            "tags": tags,
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
                "tags": tags
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


@router.post("/knowledge/intelligent")
async def create_knowledge_intelligent(
    knowledge: IntelligentKnowledgeCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new knowledge base entry with intelligent LLM-powered extraction.
    
    This endpoint:
    1. Uses LLM to analyze and categorize the content
    2. Extracts entities (characters, concepts, terms, relationships)
    3. Saves to PostgreSQL/pgvector and Qdrant
    4. Builds Neo4j graph with extracted entities
    5. Links new entities to existing ones in the graph
    """
    extraction_service = get_entity_extraction_service()
    
    try:
        # Run intelligent extraction
        result = await extraction_service.analyze_and_extract(
            content=knowledge.content,
            title=knowledge.title,
            series_id=knowledge.series_id,
            source_type=knowledge.source_type,
            existing_tags=knowledge.tags,
            language=knowledge.language
        )
        
        # Get the created knowledge entry
        if result.get("knowledge_entry_id"):
            kb_result = await db.execute(
                text("""
                    SELECT id, source_type, category, title, content, language, tags, created_at
                    FROM knowledge_base WHERE id = :id
                """),
                {"id": result["knowledge_entry_id"]}
            )
            row = kb_result.fetchone()
            
            if row:
                return {
                    "knowledge_entry": {
                        "id": row.id,
                        "source_type": row.source_type,
                        "category": row.category,
                        "title": row.title,
                        "content": row.content[:500] + "..." if len(row.content) > 500 else row.content,
                        "language": row.language,
                        "tags": row.tags or [],
                        "created_at": row.created_at
                    },
                    "extraction_result": {
                        "content_analysis": result.get("content_analysis"),
                        "entities_extracted": len(result.get("extracted_entities", [])),
                        "graph_nodes_created": len(result.get("graph_nodes_created", [])),
                        "graph_relationships_created": len(result.get("graph_relationships_created", [])),
                        "entities": result.get("extracted_entities", [])[:10],  # First 10 entities
                        "errors": result.get("errors", [])
                    },
                    "message": "Knowledge entry created with intelligent extraction"
                }
        
        raise HTTPException(status_code=500, detail="Failed to create knowledge entry")
        
    except Exception as e:
        logger.error(f"Intelligent knowledge creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


class KnowledgeUpdate(BaseModel):
    """Model for updating knowledge entries."""
    title: Optional[str] = None
    content: Optional[str] = None
    source_type: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None


@router.put("/knowledge/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    knowledge_id: int,
    update_data: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a knowledge base entry."""
    # First check if entry exists
    check_result = await db.execute(
        text("SELECT id, content FROM knowledge_base WHERE id = :knowledge_id"),
        {"knowledge_id": knowledge_id}
    )
    existing = check_result.fetchone()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    # Build dynamic update query
    update_fields = []
    params = {"knowledge_id": knowledge_id}
    
    if update_data.title is not None:
        update_fields.append("title = :title")
        params["title"] = update_data.title
    
    if update_data.content is not None:
        update_fields.append("content = :content")
        params["content"] = update_data.content
        # Regenerate embedding for content changes
        embedding = generate_embedding(update_data.content)
        update_fields.append("embedding = :embedding")
        params["embedding"] = str(embedding)
    
    if update_data.source_type is not None:
        update_fields.append("source_type = :source_type")
        params["source_type"] = update_data.source_type
    
    if update_data.category is not None:
        update_fields.append("category = :category")
        params["category"] = update_data.category
    
    if update_data.tags is not None:
        update_fields.append("tags = :tags")
        params["tags"] = update_data.tags
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Execute update
    update_query = f"""
        UPDATE knowledge_base 
        SET {', '.join(update_fields)}, updated_at = NOW()
        WHERE id = :knowledge_id
        RETURNING id, source_type, category, title, content, language, tags, created_at
    """
    
    result = await db.execute(text(update_query), params)
    await db.commit()
    row = result.fetchone()
    
    # Update Qdrant if content changed
    if update_data.content is not None:
        vector_manager = get_vector_manager()
        vector_manager.upsert_vectors(
            collection="knowledge",
            points=[{
                "id": row.id,
                "vector": embedding,
                "payload": {
                    "id": row.id,
                    "source_type": row.source_type,
                    "title": row.title,
                    "content": row.content[:500],
                    "tags": row.tags or []
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


class AskAIImproveRequest(BaseModel):
    """Request for AI improvement suggestions."""
    improvement_type: str = "general"  # general, clarity, detail, structure, consistency
    language: str = "zh-TW"
    custom_instruction: Optional[str] = None


class AskAIImproveResponse(BaseModel):
    """Response with AI improvement suggestions."""
    original_title: str
    original_content: str
    suggested_title: Optional[str] = None
    suggested_content: str
    improvement_notes: str
    changes_summary: List[str]


@router.post("/knowledge/{knowledge_id}/ask-ai-improve", response_model=AskAIImproveResponse)
async def ask_ai_improve_knowledge(
    knowledge_id: int,
    request: AskAIImproveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask AI to suggest improvements for a knowledge base entry.
    
    This does NOT modify the original entry - it returns suggestions
    that the user can review, edit, and choose to apply.
    
    Improvement types:
    - general: Overall improvements to clarity and completeness
    - clarity: Make the text clearer and more readable
    - detail: Add more specific details and examples
    - structure: Improve organization and formatting
    - consistency: Ensure consistent terminology and style
    """
    from app.services.llm_service import get_llm_service
    
    # Get the knowledge entry
    result = await db.execute(
        text("""
            SELECT id, title, content, category, source_type, tags, metadata
            FROM knowledge_base WHERE id = :id
        """),
        {"id": knowledge_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    
    original_title = row.title or "Untitled"
    original_content = row.content
    category = row.category or "worldbuilding"
    
    # Build improvement prompt based on type
    improvement_prompts = {
        "general": "Improve this text for clarity, completeness, and readability while preserving all original information.",
        "clarity": "Rewrite this text to be clearer and easier to understand. Simplify complex sentences while keeping the meaning.",
        "detail": "Expand this text with more specific details, examples, or explanations that would help a writer using this worldbuilding.",
        "structure": "Reorganize this text with better structure. Use bullet points, numbered lists, or clear sections where appropriate.",
        "consistency": "Review this text for consistency in terminology, naming conventions, and style. Suggest standardized versions."
    }
    
    instruction = improvement_prompts.get(request.improvement_type, improvement_prompts["general"])
    
    if request.custom_instruction:
        instruction += f"\n\nAdditional instruction: {request.custom_instruction}"
    
    # Language-specific prompts
    if request.language.startswith("zh"):
        system_prompt = f"""你是一位專業的小說世界觀編輯。你的任務是改進以下內容。

類別：{category}
改進方向：{instruction}

重要規則：
1. 保留所有原始信息 - 不要刪除任何內容
2. 保持原文的風格和語調
3. 用繁體中文回應
4. 如果原標題可以改進，建議一個新標題
5. 列出你做了哪些主要修改

輸出格式（嚴格遵循）：
---SUGGESTED_TITLE---
[建議的標題，如果不需要改可以填原標題]
---SUGGESTED_CONTENT---
[改進後的完整內容]
---IMPROVEMENT_NOTES---
[簡短說明你的改進方向]
---CHANGES---
- 修改1
- 修改2
- ...
---END---"""
    else:
        system_prompt = f"""You are a professional novel worldbuilding editor. Your task is to improve the following content.

Category: {category}
Improvement direction: {instruction}

Important rules:
1. Preserve all original information - do not delete anything
2. Maintain the original style and tone
3. If the original title can be improved, suggest a new one
4. List the main changes you made

Output format (follow strictly):
---SUGGESTED_TITLE---
[suggested title, or original if no change needed]
---SUGGESTED_CONTENT---
[improved full content]
---IMPROVEMENT_NOTES---
[brief explanation of your improvements]
---CHANGES---
- change 1
- change 2
- ...
---END---"""

    user_message = f"""Original Title: {original_title}

Original Content:
{original_content}"""

    # Call LLM
    llm = get_llm_service()
    try:
        response = await llm.generate([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ], temperature=0.7, max_tokens=4096)
        
        # Parse response
        import re
        
        suggested_title = original_title
        suggested_content = original_content
        improvement_notes = "AI suggestions generated"
        changes = []
        
        # Extract suggested title
        title_match = re.search(r'---SUGGESTED_TITLE---\s*([\s\S]*?)(?=---SUGGESTED_CONTENT---|$)', response)
        if title_match:
            suggested_title = title_match.group(1).strip() or original_title
        
        # Extract suggested content
        content_match = re.search(r'---SUGGESTED_CONTENT---\s*([\s\S]*?)(?=---IMPROVEMENT_NOTES---|$)', response)
        if content_match:
            suggested_content = content_match.group(1).strip() or original_content
        
        # Extract improvement notes
        notes_match = re.search(r'---IMPROVEMENT_NOTES---\s*([\s\S]*?)(?=---CHANGES---|$)', response)
        if notes_match:
            improvement_notes = notes_match.group(1).strip()
        
        # Extract changes list
        changes_match = re.search(r'---CHANGES---\s*([\s\S]*?)(?=---END---|$)', response)
        if changes_match:
            changes_text = changes_match.group(1).strip()
            changes = [line.strip().lstrip('- ') for line in changes_text.split('\n') if line.strip() and line.strip() != '-']
        
        return AskAIImproveResponse(
            original_title=original_title,
            original_content=original_content,
            suggested_title=suggested_title if suggested_title != original_title else None,
            suggested_content=suggested_content,
            improvement_notes=improvement_notes,
            changes_summary=changes
        )
        
    except Exception as e:
        logger.error(f"AI improvement failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI improvement failed: {str(e)}")


class SaveMessageRequest(BaseModel):
    session_id: UUID
    message_content: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/knowledge/from-message")
async def save_message_as_knowledge(
    request: SaveMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save a single AI response to knowledge, linked to its chat session.
    """
    # Generate embedding
    embedding = generate_embedding(request.message_content)
    
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
            "title": request.title or f"AI Response - {str(request.session_id)[:8]}",
            "content": request.message_content,
            "embedding": str(embedding),
            "tags": request.tags or ['ai-response', 'saved-from-chat'],
            "session_id": request.session_id,
            "metadata": json.dumps({"source_session_id": str(request.session_id), "type": "single_message"})
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
                "content": request.message_content[:500],
                "tags": request.tags or ['ai-response']
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

