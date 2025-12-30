"""RAG (Retrieval-Augmented Generation) service with series/story context awareness."""
from typing import List, Dict, Any, Optional
from app.services.embeddings import generate_embedding
from app.database.qdrant_client import get_vector_manager
from app.database.neo4j_client import get_graph_manager
from app.database.postgres import AsyncSessionLocal
from app.config import settings
from sqlalchemy import text
import logging
import json

logger = logging.getLogger(__name__)


class RAGService:
    """Service for retrieval-augmented generation with story context."""
    
    def __init__(self):
        self.top_k = settings.RAG_TOP_K
        self.threshold = settings.RAG_SIMILARITY_THRESHOLD
    
    async def retrieve_context(self, query: str, 
                               include_chapters: bool = True,
                               include_knowledge: bool = True,
                               include_ideas: bool = True,
                               include_graph: bool = True,
                               chapter_filter: int = None,
                               series_id: int = None) -> Dict[str, Any]:
        """Retrieve relevant context for a query with optional series filtering."""
        context = {}
        query_embedding = generate_embedding(query)
        
        # Search vector databases
        vector_manager = get_vector_manager()
        
        # Build filter for series if specified
        series_filter = None
        if series_id:
            series_filter = {"series_id": series_id}
        
        if include_chapters:
            chapter_results = vector_manager.search(
                collection="chapters",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold,
                filter_conditions=series_filter
            )
            context["chapters"] = [r["payload"] for r in chapter_results]
        
        if include_knowledge:
            # Search knowledge base - filter by series tag if available
            # Note: Also search the standalone knowledge_base collection for older data
            # Use no threshold to get all results, then filter by score manually
            knowledge_results = vector_manager.search(
                collection="knowledge",  # Maps to novel_knowledge in qdrant_client
                query_vector=query_embedding,
                limit=self.top_k * 2,  # Get more results
                score_threshold=None  # No threshold - get all results
            )
            logger.info(f"Knowledge search (novel_knowledge): {len(knowledge_results)} results")
            
            # Also search the legacy knowledge_base collection
            try:
                legacy_results = vector_manager.search(
                    collection="knowledge_base",  # Direct collection name
                    query_vector=query_embedding,
                    limit=self.top_k * 2,
                    score_threshold=None  # No threshold
                )
                logger.info(f"Knowledge search (knowledge_base): {len(legacy_results)} results")
                for r in legacy_results:
                    logger.debug(f"  - Score: {r.get('score', 'N/A')}, Title: {r.get('payload', {}).get('title', 'Unknown')}")
                knowledge_results.extend(legacy_results)
            except Exception as e:
                logger.warning(f"Knowledge base search failed: {e}")
            
            logger.info(f"Total knowledge results before filter: {len(knowledge_results)}")
            
            # Filter by series if specified
            if series_id:
                filtered_knowledge = []
                for r in knowledge_results:
                    payload = r["payload"]
                    tags = payload.get("tags", [])
                    # Check if any tag matches series:X format
                    series_tag = f"series:{series_id}"
                    if series_tag in tags or payload.get("series_id") == series_id:
                        filtered_knowledge.append(payload)
                    elif not any(t.startswith("series:") for t in tags):
                        # Include items without series tag (general knowledge)
                        filtered_knowledge.append(payload)
                context["knowledge"] = filtered_knowledge[:self.top_k]
            else:
                context["knowledge"] = [r["payload"] for r in knowledge_results[:self.top_k]]
        
        if include_ideas:
            idea_results = vector_manager.search(
                collection="ideas",
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            context["ideas"] = [r["payload"] for r in idea_results]
        
        # Search graph database for characters, relationships, events
        if include_graph:
            try:
                graph_manager = await get_graph_manager()
                graph_results = await graph_manager.search_graph(query)
                context["graph"] = graph_results
                
                # Extract character names for detailed lookup
                character_names = [c.get("name") for c in graph_results.get("characters", [])]
                if character_names:
                    graph_context = await graph_manager.get_context_for_response(
                        characters=character_names[:3],  # Limit to top 3
                        chapter=chapter_filter
                    )
                    context["characters"] = graph_context.get("characters", [])
                    context["events"] = graph_context.get("events", [])
                    context["locations"] = graph_context.get("locations", [])
            except Exception as e:
                logger.warning(f"Graph search failed: {e}")
        
        # Also get story-specific context from PostgreSQL
        if series_id:
            story_context = await self.get_story_context(series_id, query)
            context["story_setting"] = story_context
        
        # Log what was retrieved for debugging
        self._log_context_summary(query, context)
        
        return context
    
    def _log_context_summary(self, query: str, context: Dict[str, Any]):
        """Log a summary of retrieved context for debugging."""
        separator = "-" * 60
        logger.info(f"\n{separator}")
        logger.info(f"📚 RAG CONTEXT RETRIEVED")
        logger.info(f"{separator}")
        logger.info(f"Query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
        # Count items in each category
        chapters = context.get("chapters", [])
        knowledge = context.get("knowledge", [])
        ideas = context.get("ideas", [])
        graph = context.get("graph", {})
        characters = context.get("characters", [])
        story_setting = context.get("story_setting", {})
        
        logger.info(f"Chapters: {len(chapters)} items")
        logger.info(f"Knowledge: {len(knowledge)} items")
        logger.info(f"Ideas: {len(ideas)} items")
        logger.info(f"Graph: {len(graph.get('characters', []))} characters, {len(graph.get('relationships', []))} relationships")
        logger.info(f"Character details: {len(characters)} items")
        
        if story_setting:
            ss_chars = story_setting.get("characters", [])
            ss_rules = story_setting.get("world_rules", [])
            logger.info(f"Story Setting: {len(ss_chars)} characters, {len(ss_rules)} world rules")
        
        # Log first item from knowledge if available
        if knowledge:
            first_item = knowledge[0]
            title = first_item.get("title", "No title")
            content_preview = first_item.get("content", "")[:100]
            logger.info(f"First knowledge item: '{title}' - {content_preview}...")
        
        logger.info(separator)
    
    async def get_story_context(self, series_id: int, query: str = None) -> Dict[str, Any]:
        """Get comprehensive story context from PostgreSQL for a series."""
        story_context = {
            "series": None,
            "books": [],  # Story parts/books info
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
                
                # Get books/parts for this series
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
                        "synopsis": row.synopsis[:200] if row.synopsis else ""
                    })
                
                # Get character profiles for this series with book info
                chars_result = await db.execute(
                    text("""
                        SELECT cp.name, cp.aliases, cp.description, cp.personality, cp.background, cp.goals,
                               cp.first_appearance_book, b.title as book_title
                        FROM character_profiles cp
                        LEFT JOIN books b ON cp.first_appearance_book = b.id
                        WHERE cp.series_id = :series_id
                        AND (cp.verification_status = 'approved' OR cp.verification_status IS NULL)
                        ORDER BY cp.first_appearance_book ASC NULLS LAST, cp.created_at DESC
                        LIMIT 20
                    """),
                    {"series_id": series_id}
                )
                for row in chars_result.fetchall():
                    char_data = {
                        "name": row.name,
                        "aliases": row.aliases or [],
                        "description": row.description,
                        "personality": row.personality,
                        "background": row.background,
                        "goals": row.goals
                    }
                    # Add story part info if available
                    if row.first_appearance_book and row.book_title:
                        char_data["first_appears_in"] = f"Part {row.first_appearance_book}: {row.book_title}"
                    story_context["characters"].append(char_data)
                
                # Get world rules for this series
                rules_result = await db.execute(
                    text("""
                        SELECT rule_name, rule_category, rule_description
                        FROM world_rules 
                        WHERE series_id = :series_id
                        ORDER BY created_at DESC
                        LIMIT 15
                    """),
                    {"series_id": series_id}
                )
                for row in rules_result.fetchall():
                    story_context["world_rules"].append({
                        "name": row.rule_name,
                        "category": row.rule_category,
                        "description": row.rule_description
                    })
                
                # Get cultivation realms from knowledge base
                realms_result = await db.execute(
                    text("""
                        SELECT title, content
                        FROM knowledge_base 
                        WHERE category = 'cultivation_realm'
                        AND :series_tag = ANY(tags)
                        ORDER BY title
                        LIMIT 20
                    """),
                    {"series_tag": f"series:{series_id}"}
                )
                for row in realms_result.fetchall():
                    story_context["cultivation_realms"].append({
                        "title": row.title,
                        "content": row.content[:300] if row.content else ""
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
                        "content": row.content[:200] if row.content else "",
                        "category": row.category
                    })
                
        except Exception as e:
            logger.error(f"Failed to get story context: {e}")
        
        return story_context
    
    async def get_neo4j_story_context(self, series_id: int, query: str = None) -> Dict[str, Any]:
        """Get story context from Neo4j graph for a series."""
        graph_context = {
            "characters": [],
            "relationships": [],
            "concepts": [],
            "timeline_events": []
        }
        
        try:
            # Use sync driver for Neo4j (same as entity extraction)
            from neo4j import GraphDatabase
            from app.config import settings
            
            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            
            with driver.session() as session:
                # Get characters for this series
                chars_result = session.run("""
                    MATCH (c:Character)
                    WHERE c.series_id = $series_id OR c.series_id IS NULL
                    OPTIONAL MATCH (c)-[r]->(other:Character)
                    RETURN c.name as name, c.description as description, 
                           c.generation as generation, c.faction as faction,
                           collect({type: type(r), target: other.name}) as relationships
                    LIMIT 25
                """, series_id=series_id)
                
                for record in chars_result:
                    graph_context["characters"].append({
                        "name": record["name"],
                        "description": record["description"],
                        "generation": record["generation"],
                        "faction": record["faction"],
                        "relationships": [r for r in record["relationships"] if r["target"]]
                    })
                
                # Get concepts
                concepts_result = session.run("""
                    MATCH (c:Concept)
                    WHERE c.series_id = $series_id OR c.series_id IS NULL
                    RETURN c.name as name, c.definition as definition, c.type as type
                    LIMIT 20
                """, series_id=series_id)
                
                for record in concepts_result:
                    graph_context["concepts"].append({
                        "name": record["name"],
                        "definition": record["definition"],
                        "type": record["type"]
                    })
                
                # Get world rules
                rules_result = session.run("""
                    MATCH (r:WorldRule)
                    WHERE r.series_id = $series_id OR r.series_id IS NULL
                    RETURN r.name as name, r.description as description, r.category as category
                    LIMIT 15
                """, series_id=series_id)
                
                for record in rules_result:
                    if record["name"]:
                        graph_context["concepts"].append({
                            "name": record["name"],
                            "definition": record["description"],
                            "type": "world_rule"
                        })
                
                # Get cultivation realms
                realms_result = session.run("""
                    MATCH (r:CultivationRealm)
                    RETURN r.name as name, r.description as description, r.tier as tier
                    ORDER BY r.tier
                    LIMIT 20
                """)
                
                for record in realms_result:
                    if record["name"]:
                        graph_context["concepts"].append({
                            "name": record["name"],
                            "definition": record["description"],
                            "type": "cultivation_realm",
                            "tier": record["tier"]
                        })
            
            driver.close()
            
        except Exception as e:
            logger.warning(f"Neo4j story context failed: {e}")
        
        return graph_context
    
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
        """Retrieve relevant knowledge base entries."""
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        filter_conditions = {}
        if source_type:
            filter_conditions["source_type"] = source_type
        
        results = vector_manager.search(
            collection="knowledge",
            query_vector=query_embedding,
            limit=limit or self.top_k,
            score_threshold=self.threshold,
            filter_conditions=filter_conditions if filter_conditions else None
        )
        
        return [{"score": r["score"], **r["payload"]} for r in results]
    
    async def hybrid_search(self, query: str, 
                           collections: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Perform hybrid search across multiple collections."""
        if collections is None:
            collections = ["chapters", "knowledge", "ideas"]
        
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        results = {}
        for collection in collections:
            search_results = vector_manager.search(
                collection=collection,
                query_vector=query_embedding,
                limit=self.top_k,
                score_threshold=self.threshold
            )
            results[collection] = [{"score": r["score"], **r["payload"]} for r in search_results]
        
        return results
    
    async def search_by_chapter_range(self, query: str, 
                                      start_chapter: int, 
                                      end_chapter: int) -> List[Dict[str, Any]]:
        """Search within a specific chapter range."""
        query_embedding = generate_embedding(query)
        vector_manager = get_vector_manager()
        
        # Get all chapters in range, then filter by similarity
        results = vector_manager.search(
            collection="chapters",
            query_vector=query_embedding,
            limit=self.top_k * 2,  # Get more and filter
            score_threshold=self.threshold,
            filter_conditions={
                "chapter_number": list(range(start_chapter, end_chapter + 1))
            }
        )
        
        return [{"score": r["score"], **r["payload"]} for r in results]


def get_rag_service() -> RAGService:
    """Get RAG service instance."""
    return RAGService()

