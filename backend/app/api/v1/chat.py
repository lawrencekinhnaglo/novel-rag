"""Chat API endpoints with full novel awareness, multi-language support, and intent detection."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
import json
import asyncio
import logging

from app.database.postgres import get_db
from app.database.redis_client import get_conversation_cache
from app.services.llm_service import get_llm_service
from app.services.rag_service import get_rag_service
from app.services.web_search import get_web_search_service
from app.services.embeddings import generate_embedding
from app.services.document_service import get_long_context_manager
from app.services.story_analysis import get_story_analysis_service
from app.services.intent_service import get_intent_service, IntentType, DetectedIntent, FunctionResult
from app.services.series_detection import get_series_detection_service, SeriesMatch
from app.api.v1.models import ChatRequest, ChatResponse, FeedbackCreate, FeedbackResponse, LikedQAPair
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


async def auto_sync_to_knowledge(session_id, db: AsyncSession):
    """
    Auto-sync new messages to knowledge base if sync is enabled for this session.
    Called after each new message pair is saved.
    """
    try:
        # Check if sync is enabled for this session
        result = await db.execute(
            text("""
                SELECT knowledge_sync_enabled, synced_knowledge_id, last_synced_message_id
                FROM chat_sessions WHERE id = :session_id
            """),
            {"session_id": session_id}
        )
        session = result.fetchone()
        
        if not session or not session.knowledge_sync_enabled or not session.synced_knowledge_id:
            return  # Sync not enabled
        
        # Get all messages (to rebuild full content)
        msg_result = await db.execute(
            text("""
                SELECT id, role, content
                FROM chat_messages
                WHERE session_id = :session_id
                ORDER BY created_at ASC
            """),
            {"session_id": session_id}
        )
        messages = msg_result.fetchall()
        
        if not messages:
            return
        
        # Format content
        content_parts = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            content_parts.append(f"**{role_label}**: {msg.content}")
        
        full_content = "\n\n".join(content_parts)
        last_message_id = messages[-1].id
        
        # Skip if no new messages since last sync
        if session.last_synced_message_id and last_message_id <= session.last_synced_message_id:
            return
        
        # Generate new embedding
        embedding = generate_embedding(full_content)
        
        # Update knowledge entry
        await db.execute(
            text("""
                UPDATE knowledge_base 
                SET content = :content, embedding = :embedding, updated_at = NOW()
                WHERE id = :knowledge_id
            """),
            {
                "content": full_content,
                "embedding": str(embedding),
                "knowledge_id": session.synced_knowledge_id
            }
        )
        
        # Update last synced message ID
        await db.execute(
            text("""
                UPDATE chat_sessions 
                SET last_synced_message_id = :last_msg_id
                WHERE id = :session_id
            """),
            {"last_msg_id": last_message_id, "session_id": session_id}
        )
        
        # Update Qdrant
        from app.database.qdrant_client import get_vector_manager
        vector_manager = get_vector_manager()
        
        # Get title for Qdrant payload
        title_result = await db.execute(
            text("SELECT title FROM knowledge_base WHERE id = :kid"),
            {"kid": session.synced_knowledge_id}
        )
        title_row = title_result.fetchone()
        
        vector_manager.upsert_vectors(
            collection="knowledge",
            points=[{
                "id": session.synced_knowledge_id,
                "vector": embedding,
                "payload": {
                    "id": session.synced_knowledge_id,
                    "source_type": "chat",
                    "title": title_row.title if title_row else "Synced Chat",
                    "content": full_content[:500],
                    "tags": ['chat-synced', 'auto-updated']
                }
            }]
        )
        
        logger.info(f"Auto-synced session {session_id} to knowledge {session.synced_knowledge_id}")
        
    except Exception as e:
        logger.error(f"Auto-sync failed for session {session_id}: {e}")

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
    
    # Search in knowledge collection - no threshold to ensure we find relevant Chinese text
    results = vector_manager.search(
        collection="knowledge",
        query_vector=query_embedding,
        limit=30,  # Get more results for better coverage
        score_threshold=None,  # Let LLM decide relevance
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


async def get_character_profiles(db: AsyncSession, query: str, series_id: int = None) -> List[Dict]:
    """Get relevant character profiles from the database (only approved ones), optionally filtered by series."""
    # Build query with optional series filter
    if series_id:
        result = await db.execute(
            text("""
                SELECT name, description, personality, appearance, background, 
                       goals, relationships_summary, first_appearance_book, first_appearance_chapter
                FROM character_profiles
                WHERE series_id = :series_id
                   AND (name ILIKE :pattern 
                       OR description ILIKE :pattern
                       OR personality ILIKE :pattern
                       OR aliases::text ILIKE :pattern)
                   AND (verification_status = 'approved' OR verification_status IS NULL)
                LIMIT 10
            """),
            {"pattern": f"%{query}%", "series_id": series_id}
        )
    else:
        result = await db.execute(
            text("""
                SELECT name, description, personality, appearance, background, 
                       goals, relationships_summary, first_appearance_book, first_appearance_chapter
                FROM character_profiles
                WHERE (name ILIKE :pattern 
                   OR description ILIKE :pattern
                   OR personality ILIKE :pattern)
                   AND (verification_status = 'approved' OR verification_status IS NULL)
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
            "first_appearance": f"Book {row.first_appearance_book or '?'}, Chapter {row.first_appearance_chapter or '?'}" if row.first_appearance_book or row.first_appearance_chapter else None
        }
        for row in rows
    ]


# =============================================================================
# Intent-Based Function Handlers
# =============================================================================

async def handle_create_character(intent: DetectedIntent, db: AsyncSession) -> FunctionResult:
    """Handle character creation intent."""
    params = intent.parameters
    name = params.get("name", "Unnamed Character")
    description = params.get("description", "")
    role = params.get("role", "supporting")
    
    try:
        result = await db.execute(
            text("""
                INSERT INTO character_profiles (series_id, name, description, personality, verification_status)
                VALUES (1, :name, :description, :role, 'pending')
                RETURNING id
            """),
            {"name": name, "description": description, "role": role}
        )
        await db.commit()
        char_id = result.fetchone().id
        return FunctionResult(
            success=True,
            result={"character_id": char_id, "name": name},
            message=f"✅ Created character '{name}' (ID: {char_id}). Status: pending verification.",
            should_continue_chat=True
        )
    except Exception as e:
        return FunctionResult(
            success=False,
            result=None,
            message=f"Failed to create character: {str(e)}",
            should_continue_chat=True
        )


async def handle_create_world_rule(intent: DetectedIntent, db: AsyncSession) -> FunctionResult:
    """Handle world rule creation intent."""
    params = intent.parameters
    rule = params.get("rule", intent.original_message)
    category = params.get("category", "general")
    
    try:
        result = await db.execute(
            text("""
                INSERT INTO world_rules (series_id, rule_type, name, description, verification_status)
                VALUES (1, :category, :name, :description, 'pending')
                RETURNING id
            """),
            {"category": category, "name": f"Rule: {rule[:50]}", "description": rule}
        )
        await db.commit()
        rule_id = result.fetchone().id
        return FunctionResult(
            success=True,
            result={"rule_id": rule_id},
            message=f"✅ Created world rule (ID: {rule_id}). Status: pending verification.",
            should_continue_chat=True
        )
    except Exception as e:
        return FunctionResult(
            success=False,
            result=None,
            message=f"Failed to create world rule: {str(e)}",
            should_continue_chat=True
        )


async def handle_create_foreshadowing(intent: DetectedIntent, db: AsyncSession) -> FunctionResult:
    """Handle foreshadowing creation intent."""
    params = intent.parameters
    seed_type = params.get("seed_type", "plot")
    content = params.get("content", intent.original_message)
    payoff_hint = params.get("payoff_hint", "")
    
    try:
        result = await db.execute(
            text("""
                INSERT INTO foreshadowing (series_id, seed_type, content, intended_payoff, verification_status)
                VALUES (1, :seed_type, :content, :payoff, 'pending')
                RETURNING id
            """),
            {"seed_type": seed_type, "content": content, "payoff": payoff_hint}
        )
        await db.commit()
        foreshadow_id = result.fetchone().id
        return FunctionResult(
            success=True,
            result={"foreshadowing_id": foreshadow_id},
            message=f"✅ Planted foreshadowing seed (ID: {foreshadow_id}). Status: pending verification.",
            should_continue_chat=True
        )
    except Exception as e:
        return FunctionResult(
            success=False,
            result=None,
            message=f"Failed to create foreshadowing: {str(e)}",
            should_continue_chat=True
        )


async def handle_save_to_knowledge(intent: DetectedIntent, db: AsyncSession) -> FunctionResult:
    """Handle save to knowledge base intent."""
    content = intent.parameters.get("content", intent.original_message)
    title = intent.parameters.get("title", f"Note from chat")
    
    try:
        embedding = generate_embedding(content)
        result = await db.execute(
            text("""
                INSERT INTO knowledge_base (source_type, title, content, embedding)
                VALUES ('chat', :title, :content, :embedding)
                RETURNING id
            """),
            {"title": title, "content": content, "embedding": str(embedding)}
        )
        await db.commit()
        kb_id = result.fetchone().id
        return FunctionResult(
            success=True,
            result={"knowledge_id": kb_id},
            message=f"✅ Saved to knowledge base (ID: {kb_id}).",
            should_continue_chat=False
        )
    except Exception as e:
        return FunctionResult(
            success=False,
            result=None,
            message=f"Failed to save to knowledge: {str(e)}",
            should_continue_chat=True
        )


async def handle_analyze_consistency(intent: DetectedIntent, db: AsyncSession, provider: str) -> FunctionResult:
    """Handle consistency analysis intent."""
    try:
        story_service = get_story_analysis_service(provider)
        # Get the most recent chapter content for analysis
        result = await db.execute(
            text("SELECT content FROM chapters ORDER BY updated_at DESC LIMIT 1")
        )
        row = result.fetchone()
        if row:
            analysis = await story_service.check_consistency(
                new_content=row.content,
                series_id=1
            )
            return FunctionResult(
                success=True,
                result=analysis,
                message=f"📊 Consistency Analysis:\n{json.dumps(analysis, indent=2, ensure_ascii=False)}",
                should_continue_chat=True
            )
        return FunctionResult(
            success=False,
            result=None,
            message="No chapters found to analyze.",
            should_continue_chat=True
        )
    except Exception as e:
        return FunctionResult(
            success=False,
            result=None,
            message=f"Consistency analysis failed: {str(e)}",
            should_continue_chat=True
        )


# =============================================================================
# Chat Endpoints
# =============================================================================

@router.post("/chat/detect-intent")
async def detect_intent_only(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Detect intent from a message without executing any function."""
    try:
        intent_service = get_intent_service()
        intent = await intent_service.detect_intent(request.message)
        return {
            "intent": intent.intent.value,
            "confidence": intent.confidence,
            "parameters": intent.parameters,
            "explanation": intent.explanation
        }
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")
        return {
            "intent": "chat",
            "confidence": 0.5,
            "parameters": {},
            "explanation": f"Detection failed: {str(e)}"
        }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Send a chat message with full novel context awareness and intelligent intent detection."""
    # Validate language
    language = request.language if request.language in SUPPORTED_LANGUAGES else "en"
    
    # Get or create session
    session_id = request.session_id
    if session_id:
        # Check if session exists
        existing = await db.execute(
            text("SELECT id FROM chat_sessions WHERE id = :session_id"),
            {"session_id": session_id}
        )
        if not existing.fetchone():
            # Session ID provided but doesn't exist - create it
            await db.execute(
                text("""
                    INSERT INTO chat_sessions (id, title, metadata) 
                    VALUES (:session_id, :title, :metadata)
                """),
                {
                    "session_id": session_id,
                    "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
                    "metadata": json.dumps({"language": language})
                }
            )
            await db.commit()
    else:
        # No session ID - create a new one
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
    
    # ==========================================================================
    # INTENT DETECTION with Ollama Qwen3
    # ==========================================================================
    detected_intent = None
    function_result = None
    intent_prefix = ""
    
    try:
        intent_service = get_intent_service()
        detected_intent = await intent_service.detect_intent(
            message=request.message,
            context={"language": language}
        )
        
        logger.info(f"Detected intent: {detected_intent.intent.value} (confidence: {detected_intent.confidence})")
        
        # Execute function based on intent if confidence is high enough
        if detected_intent.confidence >= 0.7:
            if detected_intent.intent == IntentType.CREATE_CHARACTER:
                function_result = await handle_create_character(detected_intent, db)
            elif detected_intent.intent == IntentType.CREATE_WORLD_RULE:
                function_result = await handle_create_world_rule(detected_intent, db)
            elif detected_intent.intent == IntentType.CREATE_FORESHADOWING:
                function_result = await handle_create_foreshadowing(detected_intent, db)
            elif detected_intent.intent == IntentType.SAVE_TO_KNOWLEDGE:
                function_result = await handle_save_to_knowledge(detected_intent, db)
            elif detected_intent.intent == IntentType.ANALYZE_CONSISTENCY:
                function_result = await handle_analyze_consistency(detected_intent, db, request.provider)
        
        # Prepare intent prefix for response
        if function_result:
            intent_prefix = f"**[{detected_intent.intent.value.upper()}]** {function_result.message}\n\n"
            if not function_result.should_continue_chat:
                # Return early if function completed the request
                return ChatResponse(
                    session_id=session_id,
                    message=intent_prefix,
                    context_used={"intent": detected_intent.intent.value},
                    sources=[]
                )
    except Exception as e:
        logger.warning(f"Intent detection/execution failed: {e}")
        # Continue with normal chat if intent detection fails
    
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
        
        # Get standard RAG context with series filtering
        rag_context = await rag_service.retrieve_context(
            query=request.message,
            include_graph=request.include_graph,
            series_id=request.series_id  # Filter by story/series context
        )
        context.update(rag_context)
        
        # Get Neo4j story context if series is specified
        if request.series_id:
            try:
                neo4j_context = await rag_service.get_neo4j_story_context(request.series_id, request.message)
                if neo4j_context:
                    context["neo4j_graph"] = neo4j_context
            except Exception as e:
                logger.warning(f"Neo4j context retrieval failed: {e}")
        
        # Note: RAG service already retrieves comprehensive knowledge via hybrid search.
        # Only add categorized knowledge if RAG didn't find much.
        rag_knowledge = context.get("knowledge", [])
        if len(rag_knowledge) < 5:
            # RAG didn't find much, supplement with categorized knowledge
            query_embedding = generate_embedding(request.message)
            categorized_knowledge = await get_categorized_knowledge(
                db, query_embedding, 
                request.categories, 
                language
            )
            seen_ids = {item.get("id") for item in rag_knowledge}
            for cat, items in categorized_knowledge.items():
                for item in items:
                    if item.get("id") not in seen_ids:
                        item["category"] = cat
                        item["source"] = "categorized_search"
                        rag_knowledge.append(item)
                        seen_ids.add(item.get("id"))
            context["knowledge"] = rag_knowledge
        
        # Get character profiles - filter by series if specified
        character_profiles = await get_character_profiles(db, request.message, request.series_id)
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
    
    # Add story position context (Improvement #4) - LLM-aware story position
    if request.series_id and request.book_id and request.chapter_number:
        try:
            story_service = get_story_analysis_service(request.provider)
            position_context = await story_service.get_chapter_position_context(
                series_id=request.series_id,
                book_id=request.book_id,
                chapter_number=request.chapter_number
            )
            context["story_position"] = position_context
        except Exception as e:
            # Log but don't fail if position context fails
            import logging
            logging.getLogger(__name__).warning(f"Failed to get position context: {e}")
    
    # Prepare liked context for the LLM
    liked_context_list = None
    if request.liked_context:
        liked_context_list = [
            {"user_question": lc.user_question, "assistant_response": lc.assistant_response}
            for lc in request.liked_context
        ]
    
    # Generate response with full context
    llm_service = get_llm_service(request.provider)
    response_text = await llm_service.generate_with_context(
        user_message=request.message,
        context=context,
        conversation_history=conversation_history,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        language=language,
        uploaded_content=request.uploaded_content,
        liked_context=liked_context_list
    )
    
    # Save messages to database and get their IDs
    user_embedding = generate_embedding(request.message)
    assistant_embedding = generate_embedding(response_text)
    
    user_msg_result = await db.execute(
        text("""
            INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
            VALUES (:session_id, 'user', :content, :embedding, :metadata)
            RETURNING id
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
    user_message_id = user_msg_result.fetchone().id
    
    assistant_msg_result = await db.execute(
        text("""
            INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
            VALUES (:session_id, 'assistant', :content, :embedding, :metadata)
            RETURNING id
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
    assistant_message_id = assistant_msg_result.fetchone().id
    
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
    
    # Prepend intent action result if any
    final_message = intent_prefix + response_text if intent_prefix else response_text
    
    # Add intent info to context
    if detected_intent:
        context["detected_intent"] = {
            "type": detected_intent.intent.value,
            "confidence": detected_intent.confidence,
            "parameters": detected_intent.parameters
        }
    
    return ChatResponse(
        session_id=session_id,
        message=final_message,
        context_used=context if context else None,
        sources=sources if sources else None,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id
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
    if session_id:
        # Check if session exists
        existing = await db.execute(
            text("SELECT id FROM chat_sessions WHERE id = :session_id"),
            {"session_id": session_id}
        )
        if not existing.fetchone():
            # Session ID provided but doesn't exist - create it
            await db.execute(
                text("""
                    INSERT INTO chat_sessions (id, title, metadata) 
                    VALUES (:session_id, :title, :metadata)
                """),
                {
                    "session_id": session_id,
                    "title": request.message[:50] + "..." if len(request.message) > 50 else request.message,
                    "metadata": json.dumps({"language": language})
                }
            )
            await db.commit()
    else:
        # No session ID - create a new one
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
            include_graph=request.include_graph,
            series_id=request.series_id  # Filter by story/series context
        )
        
        # Get Neo4j story context if series is specified
        if request.series_id:
            try:
                neo4j_context = await rag_service.get_neo4j_story_context(request.series_id, request.message)
                if neo4j_context:
                    context["neo4j_graph"] = neo4j_context
            except Exception as e:
                logger.warning(f"Neo4j context retrieval failed in stream: {e}")
        
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
        async for chunk in llm_service.stream(messages, request.temperature, request.max_tokens):
            full_response += chunk
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        # Save to database after streaming completes and get IDs
        user_embedding = generate_embedding(request.message)
        assistant_embedding = generate_embedding(full_response)
        
        user_msg_result = await db.execute(
            text("""
                INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
                VALUES (:session_id, 'user', :content, :embedding, :metadata)
                RETURNING id
            """),
            {
                "session_id": session_id, 
                "content": request.message, 
                "embedding": str(user_embedding),
                "metadata": json.dumps({"language": language})
            }
        )
        user_message_id = user_msg_result.fetchone().id
        
        assistant_msg_result = await db.execute(
            text("""
                INSERT INTO chat_messages (session_id, role, content, embedding, metadata)
                VALUES (:session_id, 'assistant', :content, :embedding, :metadata)
                RETURNING id
            """),
            {
                "session_id": session_id, 
                "content": full_response, 
                "embedding": str(assistant_embedding),
                "metadata": json.dumps({"language": language})
            }
        )
        assistant_message_id = assistant_msg_result.fetchone().id
        
        await db.execute(
            text("UPDATE chat_sessions SET updated_at = NOW() WHERE id = :session_id"),
            {"session_id": session_id}
        )
        await db.commit()
        
        # Cache messages
        await cache.cache_message(str(session_id), {"role": "user", "content": request.message})
        await cache.cache_message(str(session_id), {"role": "assistant", "content": full_response})
        
        # Send message IDs with done event
        yield f"data: {json.dumps({'type': 'done', 'user_message_id': user_message_id, 'assistant_message_id': assistant_message_id})}\n\n"
    
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


# =============================================================================
# Message Feedback (Like/Dislike) Endpoints
# =============================================================================

@router.post("/chat/feedback", response_model=FeedbackResponse)
async def create_or_update_feedback(
    feedback: FeedbackCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update feedback (like/dislike) for a Q&A pair.
    When a response is liked, it will be included in future chat context.
    When disliked, it will be removed from the liked context cache.
    """
    if feedback.feedback_type not in ['like', 'dislike']:
        raise HTTPException(status_code=400, detail="feedback_type must be 'like' or 'dislike'")
    
    # Get the user question and assistant response content
    user_msg_result = await db.execute(
        text("SELECT content FROM chat_messages WHERE id = :id AND role = 'user'"),
        {"id": feedback.user_message_id}
    )
    user_msg = user_msg_result.fetchone()
    if not user_msg:
        raise HTTPException(status_code=404, detail="User message not found")
    
    assistant_msg_result = await db.execute(
        text("SELECT content FROM chat_messages WHERE id = :id AND role = 'assistant'"),
        {"id": feedback.assistant_message_id}
    )
    assistant_msg = assistant_msg_result.fetchone()
    if not assistant_msg:
        raise HTTPException(status_code=404, detail="Assistant message not found")
    
    # Upsert feedback (insert or update if exists)
    result = await db.execute(
        text("""
            INSERT INTO message_feedback 
                (session_id, user_message_id, assistant_message_id, feedback_type, user_question, assistant_response)
            VALUES 
                (:session_id, :user_message_id, :assistant_message_id, :feedback_type, :user_question, :assistant_response)
            ON CONFLICT (assistant_message_id) 
            DO UPDATE SET 
                feedback_type = :feedback_type,
                updated_at = NOW()
            RETURNING id, session_id, user_message_id, assistant_message_id, feedback_type, user_question, assistant_response, created_at
        """),
        {
            "session_id": feedback.session_id,
            "user_message_id": feedback.user_message_id,
            "assistant_message_id": feedback.assistant_message_id,
            "feedback_type": feedback.feedback_type,
            "user_question": user_msg.content,
            "assistant_response": assistant_msg.content
        }
    )
    await db.commit()
    row = result.fetchone()
    
    return FeedbackResponse(
        id=row.id,
        session_id=row.session_id,
        user_message_id=row.user_message_id,
        assistant_message_id=row.assistant_message_id,
        feedback_type=row.feedback_type,
        user_question=row.user_question,
        assistant_response=row.assistant_response,
        created_at=row.created_at
    )


@router.get("/chat/feedback/{session_id}", response_model=List[FeedbackResponse])
async def get_session_feedback(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all feedback for a session."""
    result = await db.execute(
        text("""
            SELECT id, session_id, user_message_id, assistant_message_id, feedback_type, 
                   user_question, assistant_response, created_at
            FROM message_feedback 
            WHERE session_id = :session_id
            ORDER BY created_at ASC
        """),
        {"session_id": session_id}
    )
    rows = result.fetchall()
    
    return [
        FeedbackResponse(
            id=row.id,
            session_id=row.session_id,
            user_message_id=row.user_message_id,
            assistant_message_id=row.assistant_message_id,
            feedback_type=row.feedback_type,
            user_question=row.user_question,
            assistant_response=row.assistant_response,
            created_at=row.created_at
        )
        for row in rows
    ]


@router.get("/chat/liked-context/{session_id}", response_model=List[LikedQAPair])
async def get_liked_context(
    session_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all liked Q&A pairs for a session that can be used as context.
    These will be sent with future messages to provide better responses.
    """
    result = await db.execute(
        text("""
            SELECT user_question, assistant_response
            FROM message_feedback 
            WHERE session_id = :session_id AND feedback_type = 'like'
            ORDER BY created_at ASC
        """),
        {"session_id": session_id}
    )
    rows = result.fetchall()
    
    return [
        LikedQAPair(
            user_question=row.user_question,
            assistant_response=row.assistant_response
        )
        for row in rows
    ]


@router.delete("/chat/feedback/{assistant_message_id}")
async def delete_feedback(
    assistant_message_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete feedback for a specific assistant message."""
    result = await db.execute(
        text("DELETE FROM message_feedback WHERE assistant_message_id = :id RETURNING id"),
        {"id": assistant_message_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Feedback not found")
    
    return {"status": "deleted"}


# =============================================================================
# Series Detection Endpoints
# =============================================================================

@router.post("/chat/detect-series")
async def detect_series(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Automatically detect which series a message belongs to.
    
    Returns:
    - detected_series: The most likely series match
    - suggestions: List of possible series with confidence scores
    - is_new_series: Whether the user wants to create a new series
    """
    detection_service = get_series_detection_service()
    
    # Detect series
    match = await detection_service.detect_series(
        message=request.message,
        current_series_id=request.series_id
    )
    
    # Get all suggestions
    suggestions = await detection_service.get_series_suggestions(request.message)
    
    # If we have a match, get the series title
    series_title = None
    if match.series_id:
        result = await db.execute(
            text("SELECT title FROM series WHERE id = :id"),
            {"id": match.series_id}
        )
        row = result.fetchone()
        if row:
            series_title = row.title
    
    return {
        "detected_series": {
            "series_id": match.series_id,
            "series_title": series_title,
            "confidence": match.confidence,
            "matched_elements": match.matched_elements
        },
        "suggestions": suggestions,
        "is_new_series_request": match.is_new_series_request,
        "suggested_series_name": match.suggested_series_name
    }


@router.post("/chat/auto-context")
async def chat_with_auto_context(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with automatic series detection.
    
    If no series_id is provided, the system will:
    1. Analyze the message to detect which series it belongs to
    2. Use that series context for RAG
    3. Return the detected series info along with the response
    """
    detected_series_id = request.series_id
    detection_info = None
    
    # Auto-detect series if not provided
    if not request.series_id:
        detection_service = get_series_detection_service()
        match = await detection_service.detect_series(request.message)
        
        if match.is_new_series_request:
            # User wants to create a new series - handle specially
            detection_info = {
                "action": "create_series",
                "suggested_name": match.suggested_series_name,
                "message": f"It looks like you want to start a new story. Would you like me to create a new series called '{match.suggested_series_name or 'New Story'}'?"
            }
        elif match.series_id and match.confidence >= 0.3:
            # Use detected series
            detected_series_id = match.series_id
            
            # Get series title
            result = await db.execute(
                text("SELECT title FROM series WHERE id = :id"),
                {"id": match.series_id}
            )
            row = result.fetchone()
            
            detection_info = {
                "action": "auto_detected",
                "series_id": match.series_id,
                "series_title": row.title if row else None,
                "confidence": match.confidence,
                "matched_elements": match.matched_elements,
                "message": f"Detected context: {row.title if row else 'Unknown'} (confidence: {match.confidence:.0%})"
            }
        else:
            detection_info = {
                "action": "no_match",
                "message": "No specific story context detected. Using general knowledge."
            }
    
    # Create a modified request with the detected series
    modified_request = ChatRequest(
        session_id=request.session_id,
        message=request.message,
        use_rag=request.use_rag,
        use_web_search=request.use_web_search,
        provider=request.provider,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        include_graph=request.include_graph,
        language=request.language,
        uploaded_content=request.uploaded_content,
        categories=request.categories,
        series_id=detected_series_id,
        book_id=request.book_id,
        chapter_number=request.chapter_number,
        liked_context=request.liked_context
    )
    
    # Call the regular chat endpoint
    response = await chat(modified_request, db)
    
    # Add detection info to the response
    return {
        **response.dict(),
        "series_detection": detection_info
    }
