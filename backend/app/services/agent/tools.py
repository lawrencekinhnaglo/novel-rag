"""
Agent Toolkit - Collection of tools the agent can use.

Provides interfaces to:
- RAG search
- Knowledge management
- Web search
- Character/Plot management
- Chapter operations
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class AgentToolkit:
    """
    Collection of tools available to the agent.
    
    Each tool wraps existing services to provide a clean interface
    for the agent to use.
    """
    
    def __init__(self, db=None, rag_service=None, llm_service=None):
        self.db = db
        self.rag_service = rag_service
        self.llm_service = llm_service
    
    # ==================== Knowledge Search ====================
    
    async def search_knowledge(self, 
                              query: str, 
                              categories: List[str] = None,
                              limit: int = 20,
                              series_id: int = None) -> List[Dict[str, Any]]:
        """
        Search the knowledge base using RAG.
        
        Args:
            query: Search query
            categories: Filter by categories
            limit: Maximum results
            series_id: Filter by series
        
        Returns:
            List of matching knowledge items
        """
        if self.rag_service:
            try:
                context = await self.rag_service.retrieve_context(
                    query=query,
                    include_chapters=False,
                    include_ideas=False,
                    include_graph=False,
                    series_id=series_id
                )
                
                knowledge = context.get("knowledge", [])
                
                # Filter by categories if specified
                if categories:
                    knowledge = [
                        k for k in knowledge 
                        if k.get("category") in categories
                    ]
                
                return knowledge[:limit]
                
            except Exception as e:
                logger.error(f"Knowledge search failed: {e}")
        
        # Fallback to direct database search
        if self.db:
            return await self._search_knowledge_db(query, categories, limit, series_id)
        
        return []
    
    async def _search_knowledge_db(self, 
                                   query: str, 
                                   categories: List[str],
                                   limit: int,
                                   series_id: int) -> List[Dict[str, Any]]:
        """Direct database search for knowledge."""
        from sqlalchemy import text
        
        try:
            sql = """
                SELECT id, title, content, category, source_type, tags
                FROM knowledge_base
                WHERE (content ILIKE :pattern OR title ILIKE :pattern)
            """
            params = {"pattern": f"%{query}%"}
            
            if categories:
                sql += " AND category = ANY(:categories)"
                params["categories"] = categories
            
            if series_id:
                sql += " AND (tags @> :series_tag OR metadata->>'series_id' = :series_id_str)"
                params["series_tag"] = [f"series:{series_id}"]
                params["series_id_str"] = str(series_id)
            
            sql += f" LIMIT {limit}"
            
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "content": row.content,
                    "category": row.category,
                    "source_type": row.source_type,
                    "tags": row.tags or []
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Database knowledge search failed: {e}")
            return []
    
    async def get_character_profiles(self, query: str = None) -> List[Dict[str, Any]]:
        """Get character profiles from the database."""
        if not self.db:
            return []
        
        from sqlalchemy import text
        
        try:
            sql = "SELECT * FROM character_profiles"
            params = {}
            
            if query:
                sql += " WHERE name ILIKE :pattern OR description ILIKE :pattern"
                params["pattern"] = f"%{query}%"
            
            sql += " LIMIT 20"
            
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "name": row.name,
                    "description": row.description,
                    "attributes": row.attributes if hasattr(row, 'attributes') else {}
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Character profile fetch failed: {e}")
            return []
    
    async def get_recent_chapters(self, 
                                  series_id: int = None, 
                                  limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent chapters."""
        if not self.db:
            return []
        
        from sqlalchemy import text
        
        try:
            sql = """
                SELECT c.id, c.chapter_number, c.title, c.content, c.book_id
                FROM chapters c
            """
            params = {}
            
            if series_id:
                sql += """
                    JOIN books b ON c.book_id = b.id
                    WHERE b.series_id = :series_id
                """
                params["series_id"] = series_id
            
            sql += " ORDER BY c.chapter_number DESC LIMIT :limit"
            params["limit"] = limit
            
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "chapter_number": row.chapter_number,
                    "title": row.title,
                    "content": row.content[:2000] if row.content else "",
                    "book_id": row.book_id
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Recent chapters fetch failed: {e}")
            return []
    
    # ==================== Knowledge Management ====================
    
    async def add_knowledge(self,
                           title: str,
                           content: str,
                           category: str = "worldbuilding",
                           series_id: int = None,
                           tags: List[str] = None) -> Optional[int]:
        """Add a new knowledge item."""
        if not self.db:
            return None
        
        from sqlalchemy import text
        from app.services.embeddings import generate_embedding
        import json
        
        try:
            embedding = generate_embedding(f"{title}\n{content[:2000]}")
            
            tags = tags or []
            if series_id:
                tags.append(f"series:{series_id}")
            
            result = await self.db.execute(
                text("""
                    INSERT INTO knowledge_base 
                    (source_type, category, title, content, language, embedding, tags, metadata)
                    VALUES ('agent', :category, :title, :content, 'zh-TW', 
                            :embedding, :tags, :metadata)
                    RETURNING id
                """),
                {
                    "category": category,
                    "title": title,
                    "content": content,
                    "embedding": str(embedding),
                    "tags": tags,
                    "metadata": json.dumps({"series_id": series_id, "source": "agent"})
                }
            )
            await self.db.commit()
            
            return result.scalar_one()
            
        except Exception as e:
            logger.error(f"Add knowledge failed: {e}")
            await self.db.rollback()
            return None
    
    async def update_knowledge(self,
                              knowledge_id: int,
                              updates: Dict[str, Any]) -> bool:
        """Update an existing knowledge item."""
        if not self.db:
            return False
        
        from sqlalchemy import text
        
        try:
            set_clauses = []
            params = {"id": knowledge_id}
            
            for key, value in updates.items():
                if key in ["title", "content", "category"]:
                    set_clauses.append(f"{key} = :{key}")
                    params[key] = value
            
            if not set_clauses:
                return False
            
            sql = f"UPDATE knowledge_base SET {', '.join(set_clauses)} WHERE id = :id"
            await self.db.execute(text(sql), params)
            await self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Update knowledge failed: {e}")
            await self.db.rollback()
            return False
    
    # ==================== Plot Thread Management ====================
    
    async def get_plot_threads(self, series_id: int = None) -> List[Dict[str, Any]]:
        """Get plot threads for a series."""
        if not self.db:
            return []
        
        from sqlalchemy import text
        
        try:
            sql = "SELECT * FROM plot_threads"
            params = {}
            
            if series_id:
                sql += " WHERE series_id = :series_id"
                params["series_id"] = series_id
            
            result = await self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            return [
                {
                    "id": row.id,
                    "title": row.title,
                    "description": row.description,
                    "status": row.status,
                    "importance": row.importance if hasattr(row, 'importance') else 'medium'
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Plot threads fetch failed: {e}")
            return []
    
    async def add_plot_thread(self,
                             title: str,
                             description: str,
                             series_id: int,
                             introduced_chapter: int = None,
                             importance: str = "medium") -> Optional[str]:
        """Add a new plot thread."""
        if not self.db:
            return None
        
        from sqlalchemy import text
        import uuid
        
        try:
            thread_id = f"thread_{uuid.uuid4().hex[:8]}"
            
            await self.db.execute(
                text("""
                    INSERT INTO plot_threads 
                    (id, series_id, title, description, status, introduced_chapter, importance)
                    VALUES (:id, :series_id, :title, :description, 'open', :chapter, :importance)
                """),
                {
                    "id": thread_id,
                    "series_id": series_id,
                    "title": title,
                    "description": description,
                    "chapter": introduced_chapter,
                    "importance": importance
                }
            )
            await self.db.commit()
            
            return thread_id
            
        except Exception as e:
            logger.error(f"Add plot thread failed: {e}")
            await self.db.rollback()
            return None
    
    # ==================== Web Search ====================
    
    async def web_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Perform web search for research."""
        try:
            from app.services.web_search import get_web_search_service
            service = get_web_search_service()
            return service.search(query, max_results=max_results)
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    # ==================== Chapter Operations ====================
    
    async def save_chapter(self,
                          book_id: int,
                          chapter_number: int,
                          title: str,
                          content: str) -> Optional[int]:
        """Save a chapter."""
        if not self.db:
            return None
        
        from sqlalchemy import text
        from app.services.embeddings import generate_embedding
        
        try:
            embedding = generate_embedding(f"{title}\n{content[:2000]}")
            
            result = await self.db.execute(
                text("""
                    INSERT INTO chapters (book_id, chapter_number, title, content, embedding)
                    VALUES (:book_id, :chapter_number, :title, :content, :embedding)
                    ON CONFLICT (book_id, chapter_number) DO UPDATE SET
                        title = :title, content = :content, embedding = :embedding, updated_at = NOW()
                    RETURNING id
                """),
                {
                    "book_id": book_id,
                    "chapter_number": chapter_number,
                    "title": title,
                    "content": content,
                    "embedding": str(embedding)
                }
            )
            await self.db.commit()
            
            return result.scalar_one()
            
        except Exception as e:
            logger.error(f"Save chapter failed: {e}")
            await self.db.rollback()
            return None
    
    async def get_chapter(self, chapter_id: int) -> Optional[Dict[str, Any]]:
        """Get a chapter by ID."""
        if not self.db:
            return None
        
        from sqlalchemy import text
        
        try:
            result = await self.db.execute(
                text("SELECT * FROM chapters WHERE id = :id"),
                {"id": chapter_id}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.id,
                    "book_id": row.book_id,
                    "chapter_number": row.chapter_number,
                    "title": row.title,
                    "content": row.content
                }
            return None
            
        except Exception as e:
            logger.error(f"Get chapter failed: {e}")
            return None
    
    # ==================== Series/Book Info ====================
    
    async def get_series_info(self, series_id: int) -> Optional[Dict[str, Any]]:
        """Get series information."""
        if not self.db:
            return None
        
        from sqlalchemy import text
        
        try:
            result = await self.db.execute(
                text("SELECT * FROM series WHERE id = :id"),
                {"id": series_id}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.id,
                    "title": row.title,
                    "premise": row.premise if hasattr(row, 'premise') else None,
                    "language": row.language if hasattr(row, 'language') else 'zh-TW'
                }
            return None
            
        except Exception as e:
            logger.error(f"Get series info failed: {e}")
            return None
    
    async def get_book_info(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get book information."""
        if not self.db:
            return None
        
        from sqlalchemy import text
        
        try:
            result = await self.db.execute(
                text("SELECT * FROM books WHERE id = :id"),
                {"id": book_id}
            )
            row = result.fetchone()
            
            if row:
                return {
                    "id": row.id,
                    "series_id": row.series_id,
                    "title": row.title,
                    "book_number": row.book_number if hasattr(row, 'book_number') else None
                }
            return None
            
        except Exception as e:
            logger.error(f"Get book info failed: {e}")
            return None
