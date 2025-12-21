"""Chat API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any
from uuid import UUID, uuid4
import json
import asyncio

from app.database.postgres import get_db
from app.database.redis_client import get_conversation_cache
from app.services.llm_service import get_llm_service
from app.services.rag_service import get_rag_service
from app.services.web_search import get_web_search_service
from app.services.embeddings import generate_embedding
from app.api.v1.models import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a chat message and get a response."""
    # Get or create session
    session_id = request.session_id
    if not session_id:
        result = await db.execute(
            text("""
                INSERT INTO chat_sessions (title) 
                VALUES (:title)
                RETURNING id
            """),
            {"title": request.message[:50] + "..." if len(request.message) > 50 else request.message}
        )
        await db.commit()
        session_id = result.fetchone().id
    
    # Get conversation cache
    cache = await get_conversation_cache()
    
    # Get conversation history
    history = await cache.get_messages(str(session_id), 10)
    conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history
    ]
    
    # Retrieve RAG context if enabled
    context = {}
    sources = []
    
    if request.use_rag:
        rag_service = get_rag_service()
        context = await rag_service.retrieve_context(
            query=request.message,
            include_graph=request.include_graph
        )
        sources.extend([
            {"type": "chapter", "title": ch.get("title", ""), "score": ch.get("score", 0)}
            for ch in context.get("chapters", [])
        ])
        sources.extend([
            {"type": "knowledge", "title": kb.get("title", ""), "score": kb.get("score", 0)}
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
    
    # Generate response
    llm_service = get_llm_service(request.provider)
    response_text = await llm_service.generate_with_context(
        user_message=request.message,
        context=context,
        conversation_history=conversation_history,
        temperature=request.temperature
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
            "metadata": json.dumps({"use_rag": request.use_rag, "use_web_search": request.use_web_search})
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
            "metadata": json.dumps({"provider": request.provider or "default", "sources_count": len(sources)})
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
    """Stream a chat response."""
    # Get or create session
    session_id = request.session_id
    if not session_id:
        result = await db.execute(
            text("""
                INSERT INTO chat_sessions (title) 
                VALUES (:title)
                RETURNING id
            """),
            {"title": request.message[:50] + "..." if len(request.message) > 50 else request.message}
        )
        await db.commit()
        session_id = result.fetchone().id
    
    # Get conversation cache
    cache = await get_conversation_cache()
    
    # Get conversation history
    history = await cache.get_messages(str(session_id), 10)
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
    
    # Web search if enabled
    if request.use_web_search:
        search_service = get_web_search_service()
        web_results = search_service.search(request.message, max_results=3)
        context["web_search"] = web_results
    
    async def generate():
        llm_service = get_llm_service(request.provider)
        full_response = ""
        
        # Build messages
        system_prompt = llm_service._build_novel_system_prompt()
        if context:
            context_text = llm_service._format_context(context)
            system_prompt += f"\n\n## Retrieved Context:\n{context_text}"
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-10:])
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
                INSERT INTO chat_messages (session_id, role, content, embedding)
                VALUES (:session_id, 'user', :content, :embedding)
            """),
            {"session_id": session_id, "content": request.message, "embedding": str(user_embedding)}
        )
        
        await db.execute(
            text("""
                INSERT INTO chat_messages (session_id, role, content, embedding)
                VALUES (:session_id, 'assistant', :content, :embedding)
            """),
            {"session_id": session_id, "content": full_response, "embedding": str(assistant_embedding)}
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

