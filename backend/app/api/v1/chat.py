"""Chat API endpoints with full novel awareness and multi-language support."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any, List
from uuid import UUID, uuid4
import json
import asyncio

from app.database.postgres import get_db
from app.database.redis_client import get_conversation_cache
from app.services.llm_service import get_llm_service
from app.services.rag_service import get_rag_service
from app.services.web_search import get_web_search_service
from app.services.embeddings import generate_embedding
from app.services.document_service import get_long_context_manager
from app.api.v1.models import ChatRequest, ChatResponse

router = APIRouter()

# Supported languages
SUPPORTED_LANGUAGES = ["en", "zh-TW", "zh-CN"]


async def get_categorized_knowledge(db: AsyncSession, query_embedding: List[float], 
                                     categories: List[str] = None, 
                                     language: str = None) -> Dict[str, List[Dict]]:
    """Retrieve knowledge organized by category."""
    from app.database.qdrant_client import get_vector_manager
    
    vector_manager = get_vector_manager()
    
    # Build filter conditions
    filter_conditions = {}
    if categories:
        filter_conditions["category"] = categories
    if language:
        filter_conditions["language"] = language
    
    # Search in knowledge collection
    results = vector_manager.search(
        collection="knowledge",
        query_vector=query_embedding,
        limit=20,
        score_threshold=0.5,
        filter_conditions=filter_conditions if filter_conditions else None
    )
    
    # Organize by category
    categorized = {}
    for r in results:
        payload = r["payload"]
        cat = payload.get("category", "other")
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append({
            "id": payload.get("id"),
            "title": payload.get("title", "Untitled"),
            "content": payload.get("content", ""),
            "score": r["score"],
            "category": cat
        })
    
    return categorized


async def get_character_profiles(db: AsyncSession, query: str) -> List[Dict]:
    """Get relevant character profiles from the database."""
    # Search for characters mentioned in the query
    result = await db.execute(
        text("""
            SELECT name, description, personality, appearance, background, 
                   goals, relationships_summary, first_appearance
            FROM character_profiles
            WHERE name ILIKE :pattern 
               OR description ILIKE :pattern
               OR personality ILIKE :pattern
            LIMIT 5
        """),
        {"pattern": f"%{query}%"}
    )
    rows = result.fetchall()
    
    return [
        {
            "name": row.name,
            "description": row.description,
            "personality": row.personality,
            "appearance": row.appearance,
            "background": row.background,
            "goals": row.goals,
            "relationships_summary": row.relationships_summary,
            "first_appearance": row.first_appearance
        }
        for row in rows
    ]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a chat message with full novel context awareness."""
    # Validate language
    language = request.language if request.language in SUPPORTED_LANGUAGES else "en"
    
    # Get or create session
    session_id = request.session_id
    if not session_id:
        result = await db.execute(
            text("""
                INSERT INTO chat_sessions (title, metadata) 
                VALUES (:title, :metadata)
                RETURNING id
            """),
            {
                "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
                "metadata": json.dumps({"language": language})
            }
        )
        await db.commit()
        session_id = result.fetchone().id
    
    # Get conversation cache
    cache = await get_conversation_cache()
    
    # Get conversation history (more for long context)
    history = await cache.get_messages(str(session_id), 20)
    conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history
    ]
    
    # Retrieve comprehensive context
    context = {}
    sources = []
    
    if request.use_rag:
        rag_service = get_rag_service()
        
        # Get standard RAG context
        rag_context = await rag_service.retrieve_context(
            query=request.message,
            include_graph=request.include_graph
        )
        context.update(rag_context)
        
        # Get categorized knowledge
        query_embedding = generate_embedding(request.message)
        categorized_knowledge = await get_categorized_knowledge(
            db, query_embedding, 
            request.categories, 
            language
        )
        context["knowledge"] = []
        for cat, items in categorized_knowledge.items():
            for item in items:
                item["category"] = cat
                context["knowledge"].append(item)
        
        # Get character profiles
        character_profiles = await get_character_profiles(db, request.message)
        if character_profiles:
            if "characters" not in context:
                context["characters"] = []
            context["characters"].extend(character_profiles)
        
        # Add to sources
        sources.extend([
            {"type": "chapter", "title": ch.get("title", ""), "score": ch.get("score", 0)}
            for ch in context.get("chapters", [])
        ])
        sources.extend([
            {"type": kb.get("category", "knowledge"), "title": kb.get("title", ""), "score": kb.get("score", 0)}
            for kb in context.get("knowledge", [])
        ])
    
    # Web search if enabled
    if request.use_web_search:
        search_service = get_web_search_service()
        web_results = search_service.search(request.message, max_results=3)
        context["web_search"] = web_results
        sources.extend([
            {"type": "web", "title": r.get("title", ""), "url": r.get("url", "")}
            for r in web_results
        ])
    
    # Generate response with full context
    llm_service = get_llm_service(request.provider)
    response_text = await llm_service.generate_with_context(
        user_message=request.message,
        context=context,
        conversation_history=conversation_history,
        temperature=request.temperature,
        language=language,
        uploaded_content=request.uploaded_content
    )
    
    # Save messages to database
    user_embedding = generate_embedding(request.message)
    assistant_embedding = generate_embedding(response_text)
    
    await db.execute(
        text("""
            INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
            VALUES (:session_id, 'user', :content, :embedding, :metadata)
        """),
        {
            "session_id": session_id,
            "content": request.message,
            "embedding": str(user_embedding),
            "metadata": json.dumps({
                "use_rag": request.use_rag, 
                "use_web_search": request.use_web_search,
                "language": language,
                "has_upload": bool(request.uploaded_content)
            })
        }
    )
    
    await db.execute(
        text("""
            INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
            VALUES (:session_id, 'assistant', :content, :embedding, :metadata)
        """),
        {
            "session_id": session_id,
            "content": response_text,
            "embedding": str(assistant_embedding),
            "metadata": json.dumps({
                "provider": request.provider or "default", 
                "sources_count": len(sources),
                "language": language
            })
        }
    )
    
    # Update session timestamp
    await db.execute(
        text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :session_id"),
        {"session_id": session_id}
    )
    await db.commit()
    
    # Cache messages
    await cache.cache_message(str(session_id), {
        "role": "user",
        "content": request.message
    })
    await cache.cache_message(str(session_id), {
        "role": "assistant",
        "content": response_text
    })
    
    # Cache context for this session
    if context:
        await cache.cache_context(str(session_id), context)
    
    return ChatResponse(
        session_id=session_id,
        message=response_text,
        context_used=context if context else None,
        sources=sources if sources else None
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Stream a chat response with full novel awareness."""
    language = request.language if request.language in SUPPORTED_LANGUAGES else "en"
    
    # Get or create session
    session_id = request.session_id
    if not session_id:
        result = await db.execute(
            text("""
                INSERT INTO chat_sessions (title, metadata) 
                VALUES (:title, :metadata)
                RETURNING id
            """),
            {
                "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
                "metadata": json.dumps({"language": language})
            }
        )
        await db.commit()
        session_id = result.fetchone().id
    
    # Get conversation cache
    cache = await get_conversation_cache()
    
    # Get conversation history
    history = await cache.get_messages(str(session_id), 20)
    conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history
    ]
    
    # Retrieve RAG context if enabled
    context = {}
    if request.use_rag:
        rag_service = get_rag_service()
        context = await rag_service.retrieve_context(
            query=request.message,
            include_graph=request.include_graph
        )
        
        # Get categorized knowledge
        query_embedding = generate_embedding(request.message)
        categorized_knowledge = await get_categorized_knowledge(
            db, query_embedding, 
            request.categories, 
            language
        )
        context["knowledge"] = []
        for cat, items in categorized_knowledge.items():
            for item in items:
                item["category"] = cat
                context["knowledge"].append(item)
    
    # Web search if enabled
    if request.use_web_search:
        search_service = get_web_search_service()
        web_results = search_service.search(request.message, max_results=3)
        context["web_search"] = web_results
    
    async def generate():
        llm_service = get_llm_service(request.provider)
        full_response = ""
        
        # Build messages with language support
        system_prompt = llm_service._build_novel_system_prompt(language)
        if context:
            context_text = llm_service._format_context(context, language)
            system_prompt += f"\n\n## Retrieved Context:\n{context_text}"
        
        # Add uploaded content if present
        if request.uploaded_content:
            upload_header = {
                "en": "## Uploaded Document Content:",
                "zh-TW": "## 上傳的文件內容：",
                "zh-CN": "## 上传的文档内容："
            }.get(language, "## Uploaded Document Content:")
            system_prompt += f"\n\n{upload_header}\n{request.uploaded_content[:8000]}"
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-20:])
        messages.append({"role": "user", "content": request.message})
        
        # Send session_id first
        yield f"data: {json.dumps({'type': 'session', 'session_id': str(session_id)})}\n\n"
        
        # Stream response
        async for chunk in llm_service.stream(messages, request.temperature):
            full_response += chunk
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        # Save to database after streaming completes
        user_embedding = generate_embedding(request.message)
        assistant_embedding = generate_embedding(full_response)
        
        await db.execute(
            text("""
                INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
                VALUES (:session_id, 'user', :content, :embedding, :metadata)
            """),
            {
                "session_id": session_id, 
                "content": request.message, 
                "embedding": str(user_embedding),
                "metadata": json.dumps({"language": language})
            }
        )
        
        await db.execute(
            text("""
                INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
                VALUES (:session_id, 'assistant', :content, :embedding, :metadata)
            """),
            {
                "session_id": session_id, 
                "content": full_response, 
                "embedding": str(assistant_embedding),
                "metadata": json.dumps({"language": language})
            }
        )
        
        await db.execute(
            text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :session_id"),
            {"session_id": session_id}
        )
        await db.commit()
        
        # Cache messages
        await cache.cache_message(str(session_id), {"role": "user", "content": request.message})
        await cache.cache_message(str(session_id), {"role": "assistant", "content": full_response})
        
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/chat/context/{session_id}")
async def get_chat_context(
    session_id: UUID
):
    """Get the cached context for a chat session."""
    cache = await get_conversation_cache()
    context = await cache.get_context(str(session_id))
    
    if not context:
        raise HTTPException(status_code=404, detail="No cached context found")
    
    return context


@router.get("/chat/languages")
async def get_supported_languages():
    """Get list of supported languages."""
    return {
        "languages": {
            "en": "English",
            "zh-TW": "繁體中文 (Traditional Chinese)",
            "zh-CN": "简体中文 (Simplified Chinese)"
        },
        "default": "en"
    }
