"""
Enhanced RAG (Retrieval-Augmented Generation) service with hybrid search, re-ranking, and intent detection.
Optimized for Chinese text and creative writing assistance.
"""
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
from app.services.embeddings import (
    generate_embedding, 
    get_bm25_index, 
    hybrid_search as do_hybrid_fusion,
    rerank_results,
    extract_keywords,
    BM25Index
)
from app.database.qdrant_client import get_vector_manager
from app.database.neo4j_client import get_graph_manager
from app.database.postgres import AsyncSessionLocal
from app.config import settings
from sqlalchemy import text
import logging
import json
import re

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Types of user queries."""
    WRITE_CHAPTER = "write_chapter"  # "Write chapter 1 of book 1"
    WRITE_CONTENT = "write_content"  # General writing request
    ASK_CHARACTER = "ask_character"  # "Who is X?"
    ASK_WORLDBUILDING = "ask_worldbuilding"  # "What is the cultivation system?"
    ASK_PLOT = "ask_plot"  # "What happens in book 3?"
    GENERAL_QUESTION = "general"  # Other questions
    EDIT_CONTENT = "edit_content"  # Edit/improve existing content


class IntentAnalyzer:
    """Analyze user query to determine intent and extract parameters."""
    
    @staticmethod
    def analyze(query: str) -> Dict[str, Any]:
        """Analyze query and return intent with extracted parameters."""
        query_lower = query.lower()
        
        # Chinese patterns for writing
        write_patterns = [
            r'寫[第]?(\d+|[一二三四五六七八九十]+)[部]?[第]?(\d+|[一二三四五六七八九十]+)?章',
            r'寫.*章',
            r'幫我寫',
            r'創作',
            r'撰寫',
            r'write.*chapter',
            r'write.*part'
        ]
        
        # Detect writing intent
        for pattern in write_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Extract book and chapter numbers
                book_num = None
                chapter_num = None
                
                # Extract numbers from query
                num_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
                
                book_match = re.search(r'第[一二三四五六七八九十\d]+部', query)
                if book_match:
                    num_str = book_match.group()
                    for cn, ar in num_map.items():
                        if cn in num_str:
                            book_num = ar
                            break
                    if not book_num:
                        digit_match = re.search(r'\d+', num_str)
                        if digit_match:
                            book_num = int(digit_match.group())
                
                chapter_match = re.search(r'第[一二三四五六七八九十\d]+章', query)
                if chapter_match:
                    num_str = chapter_match.group()
                    for cn, ar in num_map.items():
                        if cn in num_str:
                            chapter_num = ar
                            break
                    if not chapter_num:
                        digit_match = re.search(r'\d+', num_str)
                        if digit_match:
                            chapter_num = int(digit_match.group())
                
                return {
                    "intent": QueryIntent.WRITE_CHAPTER,
                    "book_number": book_num or 1,
                    "chapter_number": chapter_num or 1,
                    "full_query": query
                }
        
        # Detect character questions
        character_patterns = [
            r'誰是',
            r'是誰',
            r'主角',
            r'角色',
            r'who is',
            r'character'
        ]
        for pattern in character_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return {
                    "intent": QueryIntent.ASK_CHARACTER,
                    "full_query": query
                }
        
        # Detect worldbuilding questions
        worldbuilding_patterns = [
            r'修行體系',
            r'修煉',
            r'境界',
            r'世界觀',
            r'設定',
            r'cultivation',
            r'worldbuilding',
            r'power system'
        ]
        for pattern in worldbuilding_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return {
                    "intent": QueryIntent.ASK_WORLDBUILDING,
                    "full_query": query
                }
        
        # Detect plot questions
        plot_patterns = [
            r'發生了什麼',
            r'劇情',
            r'故事',
            r'what happens',
            r'plot'
        ]
        for pattern in plot_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return {
                    "intent": QueryIntent.ASK_PLOT,
                    "full_query": query
                }
        
        # Edit/improve patterns
        edit_patterns = [
            r'改進',
            r'修改',
            r'潤色',
            r'improve',
            r'edit',
            r'revise'
        ]
        for pattern in edit_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return {
                    "intent": QueryIntent.EDIT_CONTENT,
                    "full_query": query
                }
        
        # Default to general question
        return {
            "intent": QueryIntent.GENERAL_QUESTION,
            "full_query": query
        }


class RAGService:
    """Enhanced RAG service with hybrid search and intent-aware retrieval."""
    
    def __init__(self):
        self.top_k = settings.RAG_TOP_K
        self.threshold = settings.RAG_SIMILARITY_THRESHOLD
        self.use_hybrid = settings.RAG_USE_HYBRID_SEARCH
        self.use_reranking = settings.RAG_USE_RERANKING
        self.intent_analyzer = IntentAnalyzer()
        self._bm25_initialized = False
    
    async def _ensure_bm25_index(self):
        """Ensure BM25 index is populated with knowledge base."""
        if self._bm25_initialized:
            return
        
        try:
            bm25 = get_bm25_index()
            if bm25.documents:
                self._bm25_initialized = True
                return
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT id, title, content, category FROM knowledge_base LIMIT 1000")
                )
                rows = result.fetchall()
                
                documents = []
                for row in rows:
                    documents.append({
                        "id": row.id,
                        "title": row.title or "",
                        "content": row.content or "",
                        "category": row.category or "general"
                    })
                
                if documents:
                    bm25.add_documents(documents)
                    logger.info(f"BM25 index populated with {len(documents)} documents")
                
                self._bm25_initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize BM25 index: {e}")
    
    async def retrieve_context(self, query: str, 
                               include_chapters: bool = True,
                               include_knowledge: bool = True,
                               include_ideas: bool = True,
                               include_graph: bool = True,
                               chapter_filter: int = None,
                               series_id: int = None) -> Dict[str, Any]:
        """Retrieve relevant context with intent-aware hybrid search."""
        
        # Analyze intent
        intent_result = self.intent_analyzer.analyze(query)
        intent = intent_result["intent"]
        logger.info(f"Query intent detected: {intent.value}")
        
        context = {
            "intent": intent.value,
            "intent_params": intent_result
        }
        
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        # Build filter for series
        series_filter = {"series_id": series_id} if series_id else None
        
        # Adjust retrieval based on intent
        if intent == QueryIntent.WRITE_CHAPTER:
            # For writing, get LOTS of worldbuilding context
            include_knowledge = True
            include_chapters = True  # Get previous chapters for continuity
            self.top_k = 20  # More results for writing
        elif intent == QueryIntent.ASK_CHARACTER:
            include_graph = True
        elif intent == QueryIntent.ASK_WORLDBUILDING:
            include_knowledge = True
            self.top_k = 15
        
        # Chapter retrieval
        if include_chapters:
            chapter_results = vector_manager.search(
                collection="chapters",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold,
                filter_conditions=series_filter
            )
            context["chapters"] = [r["payload"] for r in chapter_results]
        
        # Knowledge retrieval with hybrid search
        if include_knowledge:
            knowledge_items = await self._hybrid_knowledge_search(
                query, query_embedding, vector_manager, series_id, intent
            )
            
            # Re-rank if enabled
            if self.use_reranking and knowledge_items:
                knowledge_items = rerank_results(
                    query, 
                    knowledge_items, 
                    content_key='content',
                    top_k=min(20, len(knowledge_items))
                )
                logger.info(f"Re-ranked {len(knowledge_items)} knowledge items")
            
            context["knowledge"] = knowledge_items
        
        # Ideas retrieval
        if include_ideas:
            idea_results = vector_manager.search(
                collection="ideas",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            context["ideas"] = [r["payload"] for r in idea_results]
        
        # Graph retrieval
        if include_graph:
            try:
                graph_manager = await get_graph_manager()
                graph_results = await graph_manager.search_graph(query)
                context["graph"] = graph_results
                
                character_names = [c.get("name") for c in graph_results.get("characters", [])]
                if character_names:
                    graph_context = await graph_manager.get_context_for_response(
                        characters=character_names[:3],
                        chapter=chapter_filter
                    )
                    context["characters"] = graph_context.get("characters", [])
                    context["events"] = graph_context.get("events", [])
                    context["locations"] = graph_context.get("locations", [])
            except Exception as e:
                logger.warning(f"Graph search failed: {e}")
        
        # Get story-specific context for writing
        if series_id:
            story_context = await self.get_story_context(series_id, query, intent_result)
            context["story_setting"] = story_context
        
        # Add writing-specific context
        if intent == QueryIntent.WRITE_CHAPTER:
            book_num = intent_result.get("book_number", 1)
            writing_context = await self._get_writing_context(series_id, book_num, query)
            context["writing_guidance"] = writing_context
        
        self._log_context_summary(query, context)
        
        return context
    
    async def _hybrid_knowledge_search(
        self, 
        query: str, 
        query_embedding: List[float],
        vector_manager,
        series_id: int,
        intent: QueryIntent
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector and keyword search."""
        knowledge_items = []
        
        # 1. PostgreSQL keyword search (great for Chinese exact matches)
        keyword_items = await self._postgres_keyword_search(query, series_id, intent)
        knowledge_items.extend(keyword_items)
        logger.info(f"Keyword search found: {len(keyword_items)} items")
        
        # 2. BM25 search (if enabled)
        if self.use_hybrid:
            await self._ensure_bm25_index()
            bm25 = get_bm25_index()
            bm25_results = bm25.search(query, top_k=15)
            
            seen_ids = {item.get("id") for item in knowledge_items}
            for doc, score in bm25_results:
                if doc.get("id") not in seen_ids and score > 0:
                    doc_copy = doc.copy()
                    doc_copy["source"] = "bm25_search"
                    doc_copy["bm25_score"] = score
                    knowledge_items.append(doc_copy)
                    seen_ids.add(doc.get("id"))
            logger.info(f"BM25 search found: {len(bm25_results)} items")
        
        # 3. Vector search (semantic similarity)
        vector_results = vector_manager.search(
            collection="knowledge",
            query_vector=query_embedding,
            limit=25,
            score_threshold=None  # Get all, let re-ranker decide
        )
        
        seen_titles = {item.get("title") for item in knowledge_items}
        for r in vector_results:
            payload = r["payload"]
            if payload.get("title") not in seen_titles:
                knowledge_items.append({
                    "id": payload.get("id"),
                    "title": payload.get("title", "Untitled"),
                    "content": payload.get("content", "")[:3000],
                    "category": payload.get("category", "worldbuilding"),
                    "source": "vector_search",
                    "score": r.get("score", 0)
                })
                seen_titles.add(payload.get("title"))
        
        logger.info(f"Vector search found: {len(vector_results)} items")
        logger.info(f"Total unique items before filtering: {len(knowledge_items)}")
        
        # Filter by series if specified
        if series_id:
            filtered = []
            for item in knowledge_items:
                tags = item.get("tags", [])
                series_tag = f"series:{series_id}"
                if (series_tag in tags or 
                    item.get("series_id") == series_id or
                    item.get("source") in ["keyword_search", "bm25_search"]):
                    filtered.append(item)
                elif not any(str(t).startswith("series:") for t in tags):
                    filtered.append(item)
            knowledge_items = filtered
        
        return knowledge_items[:30]  # Return top 30 items
    
    async def _postgres_keyword_search(
        self, 
        query: str, 
        series_id: int,
        intent: QueryIntent
    ) -> List[Dict[str, Any]]:
        """PostgreSQL keyword search optimized for Chinese text."""
        items = []
        
        try:
            async with AsyncSessionLocal() as db:
                clean_query = re.sub(r'[?!。，、；：""''（）\[\]【】是什麼誰有的]', '', query)
                
                patterns = []
                
                # Intent-specific patterns
                if intent == QueryIntent.WRITE_CHAPTER:
                    patterns.extend([
                        "%正傳%", "%統一模板%", "%類型片指引%", "%成長線%",
                        "%主角%", "%世界觀%", "%牧者%", "%道果牧場%",
                        "%修行體系%", "%十五境%", "%核心器物%", "%陣營%"
                    ])
                    
                    # Extract book number for book-specific content
                    book_match = re.search(r'第[一二三四五六1-6]部', query)
                    if book_match:
                        num_map = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6'}
                        for cn, ar in num_map.items():
                            if cn in book_match.group():
                                patterns.append(f"%第 {ar} %")
                                patterns.append(f"%（第 {ar} 部）%")
                                patterns.append(f"%第{ar}部%")
                                break
                
                elif intent == QueryIntent.ASK_CHARACTER:
                    patterns.extend(["%主角%", "%角色%", "%代際%", "%火種三人%"])
                
                elif intent == QueryIntent.ASK_WORLDBUILDING:
                    patterns.extend([
                        "%修行體系%", "%十五境%", "%收割%", "%牧者%",
                        "%世界地圖%", "%天律網%", "%核心器物%"
                    ])
                
                # Extract Chinese terms (2-4 chars)
                terms = re.findall(r'[\u4e00-\u9fff]{2,4}', clean_query)
                skip_words = {'什麼', '怎麼', '為什', '如何', '幫我', '可以'}
                for term in terms:
                    if term not in skip_words:
                        patterns.append(f"%{term}%")
                
                # Remove duplicates
                patterns = list(dict.fromkeys(patterns))[:10]
                
                if not patterns:
                    patterns = [f"%{clean_query[:4]}%"]
                
                # Build dynamic query
                where_clauses = []
                params = {}
                for i, pattern in enumerate(patterns[:5]):  # Use top 5 patterns
                    param_name = f"p{i}"
                    where_clauses.append(f"(content ILIKE :{param_name} OR title ILIKE :{param_name})")
                    params[param_name] = pattern
                
                where_sql = " OR ".join(where_clauses)
                
                sql = f"""
                    SELECT id, title, content, category, source_type
                    FROM knowledge_base
                    WHERE {where_sql}
                    ORDER BY LENGTH(content) DESC
                    LIMIT 15
                """
                
                result = await db.execute(text(sql), params)
                rows = result.fetchall()
                
                for row in rows:
                    items.append({
                        "id": row.id,
                        "title": row.title,
                        "content": row.content[:3000] if row.content else "",
                        "category": row.category or "worldbuilding",
                        "source": "keyword_search"
                    })
                    
        except Exception as e:
            logger.error(f"PostgreSQL keyword search failed: {e}")
        
        return items
    
    async def _get_writing_context(
        self, 
        series_id: int, 
        book_number: int,
        query: str
    ) -> Dict[str, Any]:
        """Get specific context for chapter writing."""
        writing_context = {
            "book_info": None,
            "protagonist": None,
            "themes": [],
            "active_foreshadowing": [],
            "genre_guidance": None,
            "previous_chapters": []
        }
        
        try:
            async with AsyncSessionLocal() as db:
                # Get book info
                book_result = await db.execute(
                    text("""
                        SELECT id, title, theme, synopsis, metadata
                        FROM books
                        WHERE series_id = :series_id AND book_number = :book_number
                    """),
                    {"series_id": series_id, "book_number": book_number}
                )
                book = book_result.fetchone()
                if book:
                    writing_context["book_info"] = {
                        "title": book.title,
                        "theme": book.theme,
                        "synopsis": book.synopsis
                    }
                
                # Get protagonist for this book (first appearance in this book)
                protagonist_result = await db.execute(
                    text("""
                        SELECT name, description, personality, goals, background
                        FROM character_profiles
                        WHERE series_id = :series_id
                        AND first_appearance_book = :book_id
                        AND role = 'protagonist'
                        LIMIT 1
                    """),
                    {"series_id": series_id, "book_id": book.id if book else None}
                )
                protagonist = protagonist_result.fetchone()
                if protagonist:
                    writing_context["protagonist"] = {
                        "name": protagonist.name,
                        "description": protagonist.description,
                        "personality": protagonist.personality,
                        "goals": protagonist.goals,
                        "background": protagonist.background
                    }
                
                # Get active foreshadowing to plant
                foreshadowing_result = await db.execute(
                    text("""
                        SELECT hint, setup_context, payoff_context, planted_chapter, payoff_chapter
                        FROM foreshadowing
                        WHERE series_id = :series_id
                        AND planted_book = :book_number
                        AND status = 'planted'
                        LIMIT 5
                    """),
                    {"series_id": series_id, "book_number": book_number}
                )
                for row in foreshadowing_result.fetchall():
                    writing_context["active_foreshadowing"].append({
                        "hint": row.hint,
                        "setup": row.setup_context,
                        "payoff": row.payoff_context
                    })
                
                # Get genre guidance from knowledge base
                genre_result = await db.execute(
                    text("""
                        SELECT content
                        FROM knowledge_base
                        WHERE (title ILIKE '%類型片%' OR title ILIKE '%寫作指引%')
                        AND :series_tag = ANY(tags)
                        LIMIT 1
                    """),
                    {"series_tag": f"series:{series_id}"}
                )
                genre = genre_result.fetchone()
                if genre:
                    writing_context["genre_guidance"] = genre.content[:2000]
                    
        except Exception as e:
            logger.error(f"Failed to get writing context: {e}")
        
        return writing_context
    
    async def get_story_context(self, series_id: int, query: str = None, intent_result: Dict = None) -> Dict[str, Any]:
        """Get comprehensive story context from PostgreSQL."""
        story_context = {
            "series": None,
            "books": [],
            "characters": [],
            "world_rules": [],
            "cultivation_realms": [],
            "key_concepts": []
        }
        
        try:
            async with AsyncSessionLocal() as db:
                # Get series info
                series_result = await db.execute(
                    text("""
                        SELECT id, title, premise, themes, language
                        FROM series WHERE id = :series_id
                    """),
                    {"series_id": series_id}
                )
                series = series_result.fetchone()
                if series:
                    story_context["series"] = {
                        "id": series.id,
                        "title": series.title,
                        "premise": series.premise,
                        "themes": series.themes,
                        "language": series.language
                    }
                
                # Get books
                books_result = await db.execute(
                    text("""
                        SELECT id, book_number, title, theme, synopsis
                        FROM books 
                        WHERE series_id = :series_id
                        ORDER BY book_number ASC
                    """),
                    {"series_id": series_id}
                )
                for row in books_result.fetchall():
                    story_context["books"].append({
                        "part_number": row.book_number,
                        "title": row.title,
                        "theme": row.theme,
                        "synopsis": row.synopsis[:300] if row.synopsis else ""
                    })
                
                # Get characters - more if writing intent
                char_limit = 30 if (intent_result and intent_result.get("intent") == QueryIntent.WRITE_CHAPTER) else 15
                chars_result = await db.execute(
                    text("""
                        SELECT cp.name, cp.aliases, cp.description, cp.personality, cp.background, cp.goals, cp.role,
                               cp.first_appearance_book, b.title as book_title
                        FROM character_profiles cp
                        LEFT JOIN books b ON cp.first_appearance_book = b.id
                        WHERE cp.series_id = :series_id
                        ORDER BY cp.first_appearance_book ASC NULLS LAST
                        LIMIT :limit
                    """),
                    {"series_id": series_id, "limit": char_limit}
                )
                for row in chars_result.fetchall():
                    story_context["characters"].append({
                        "name": row.name,
                        "role": row.role,
                        "aliases": row.aliases or [],
                        "description": row.description,
                        "personality": row.personality,
                        "background": row.background,
                        "goals": row.goals,
                        "first_appears_in": f"Part {row.first_appearance_book}: {row.book_title}" if row.book_title else None
                    })
                
                # Get world rules
                rules_result = await db.execute(
                    text("""
                        SELECT rule_name, rule_category, rule_description
                        FROM world_rules 
                        WHERE series_id = :series_id
                        LIMIT 20
                    """),
                    {"series_id": series_id}
                )
                for row in rules_result.fetchall():
                    story_context["world_rules"].append({
                        "name": row.rule_name,
                        "category": row.rule_category,
                        "description": row.rule_description
                    })
                
                # Get cultivation realms
                realms_result = await db.execute(
                    text("""
                        SELECT title, content
                        FROM knowledge_base 
                        WHERE category = 'cultivation_realm'
                        AND :series_tag = ANY(tags)
                        LIMIT 20
                    """),
                    {"series_tag": f"series:{series_id}"}
                )
                for row in realms_result.fetchall():
                    story_context["cultivation_realms"].append({
                        "title": row.title,
                        "content": row.content[:500] if row.content else ""
                    })
                
                # Get key concepts
                concepts_result = await db.execute(
                    text("""
                        SELECT title, content, category
                        FROM knowledge_base 
                        WHERE category IN ('concept', 'world_concept', 'talent_system', 'term', 'technique')
                        AND :series_tag = ANY(tags)
                        LIMIT 15
                    """),
                    {"series_tag": f"series:{series_id}"}
                )
                for row in concepts_result.fetchall():
                    story_context["key_concepts"].append({
                        "title": row.title,
                        "content": row.content[:300] if row.content else "",
                        "category": row.category
                    })
                    
        except Exception as e:
            logger.error(f"Failed to get story context: {e}")
        
        return story_context
    
    def _log_context_summary(self, query: str, context: Dict[str, Any]):
        """Log summary of retrieved context."""
        separator = "=" * 60
        logger.info(f"\n{separator}")
        logger.info(f"RAG CONTEXT SUMMARY")
        logger.info(f"{separator}")
        logger.info(f"Query: {query[:80]}...")
        logger.info(f"Intent: {context.get('intent', 'unknown')}")
        
        chapters = context.get("chapters", [])
        knowledge = context.get("knowledge", [])
        ideas = context.get("ideas", [])
        
        logger.info(f"Chapters: {len(chapters)}")
        logger.info(f"Knowledge: {len(knowledge)}")
        logger.info(f"Ideas: {len(ideas)}")
        
        if knowledge:
            logger.info("Top knowledge items:")
            for i, item in enumerate(knowledge[:3]):
                title = item.get("title", "No title")[:50]
                source = item.get("source", "unknown")
                logger.info(f"  {i+1}. [{source}] {title}")
        
        logger.info(separator)
    
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
        """Retrieve relevant knowledge base entries with hybrid search."""
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        # Vector search
        vector_results = vector_manager.search(
            collection="knowledge",
            query_vector=query_embedding,
            limit=(limit or self.top_k) * 2,
            score_threshold=self.threshold
        )
        
        results = [{"score": r["score"], **r["payload"]} for r in vector_results]
        
        # Re-rank if enabled
        if self.use_reranking and results:
            results = rerank_results(query, results, top_k=limit or self.top_k)
        
        return results[:limit or self.top_k]


def get_rag_service() -> RAGService:
    """Get RAG service instance."""
    return RAGService()
