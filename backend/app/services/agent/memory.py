"""
Agent Memory - Long-term memory for the agent.

Stores and retrieves:
- User preferences
- Past decisions and their outcomes
- Learned patterns
- Plot threads and their status
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class MemoryItem:
    """A single memory item."""
    id: str
    type: str  # preference, decision, pattern, plot_thread, feedback
    content: Dict[str, Any]
    importance: float = 0.5  # 0-1, higher = more important
    access_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "importance": self.importance,
            "access_count": self.access_count,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class PlotThread:
    """A plot thread being tracked."""
    id: str
    title: str
    description: str
    status: str  # open, resolved, abandoned
    introduced_chapter: Optional[int] = None
    resolved_chapter: Optional[int] = None
    related_characters: List[str] = field(default_factory=list)
    importance: str = "medium"  # low, medium, high, critical
    notes: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "introduced_chapter": self.introduced_chapter,
            "resolved_chapter": self.resolved_chapter,
            "related_characters": self.related_characters,
            "importance": self.importance,
            "notes": self.notes,
            "created_at": self.created_at.isoformat()
        }


class AgentMemory:
    """
    Long-term memory system for the agent.
    
    Stores preferences, decisions, patterns, and plot threads.
    Can persist to database for cross-session memory.
    """
    
    def __init__(self, db=None, user_id: str = None, series_id: int = None):
        self.db = db
        self.user_id = user_id
        self.series_id = series_id
        
        # In-memory caches
        self._memories: Dict[str, MemoryItem] = {}
        self._plot_threads: Dict[str, PlotThread] = {}
        self._preferences: Dict[str, Any] = {}
        self._feedback_history: List[Dict[str, Any]] = []
    
    # ==================== Preferences ====================
    
    async def set_preference(self, key: str, value: Any, category: str = "general"):
        """Set a user preference."""
        self._preferences[f"{category}.{key}"] = value
        
        # Persist to database
        if self.db:
            await self._persist_preference(category, key, value)
    
    async def get_preference(self, key: str, category: str = "general", default=None) -> Any:
        """Get a user preference."""
        return self._preferences.get(f"{category}.{key}", default)
    
    async def get_all_preferences(self, category: str = None) -> Dict[str, Any]:
        """Get all preferences, optionally filtered by category."""
        if category:
            return {
                k.split(".", 1)[1]: v 
                for k, v in self._preferences.items() 
                if k.startswith(f"{category}.")
            }
        return self._preferences.copy()
    
    # ==================== Feedback Learning ====================
    
    async def record_feedback(self, 
                             task_type: str,
                             content: str,
                             feedback: str,  # positive, negative, neutral
                             details: Dict[str, Any] = None):
        """
        Record user feedback on agent output.
        Used to learn what the user likes/dislikes.
        """
        feedback_item = {
            "id": f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "task_type": task_type,
            "content_preview": content[:500],
            "feedback": feedback,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self._feedback_history.append(feedback_item)
        
        # Learn from feedback
        await self._learn_from_feedback(task_type, feedback, details)
        
        # Persist
        if self.db:
            await self._persist_feedback(feedback_item)
    
    async def _learn_from_feedback(self, task_type: str, feedback: str, details: Dict):
        """Extract patterns from feedback."""
        # Track positive/negative counts per task type
        pref_key = f"feedback_stats.{task_type}"
        stats = self._preferences.get(pref_key, {"positive": 0, "negative": 0, "neutral": 0})
        stats[feedback] = stats.get(feedback, 0) + 1
        self._preferences[pref_key] = stats
        
        # If there are specific details (e.g., "too long", "wrong tone"), track them
        if details:
            for key, value in details.items():
                pattern_key = f"learned_pattern.{task_type}.{key}"
                patterns = self._preferences.get(pattern_key, [])
                patterns.append({"value": value, "feedback": feedback})
                # Keep last 20 patterns
                self._preferences[pattern_key] = patterns[-20:]
    
    async def get_learned_preferences(self, task_type: str) -> Dict[str, Any]:
        """Get learned preferences for a task type."""
        result = {
            "feedback_stats": self._preferences.get(f"feedback_stats.{task_type}", {}),
            "patterns": {}
        }
        
        # Collect learned patterns
        for key, value in self._preferences.items():
            if key.startswith(f"learned_pattern.{task_type}."):
                pattern_name = key.split(".")[-1]
                result["patterns"][pattern_name] = value
        
        return result
    
    # ==================== Plot Threads ====================
    
    async def add_plot_thread(self, thread: PlotThread):
        """Add a new plot thread to track."""
        self._plot_threads[thread.id] = thread
        
        if self.db:
            await self._persist_plot_thread(thread)
    
    async def update_plot_thread(self, thread_id: str, updates: Dict[str, Any]):
        """Update an existing plot thread."""
        if thread_id in self._plot_threads:
            thread = self._plot_threads[thread_id]
            for key, value in updates.items():
                if hasattr(thread, key):
                    setattr(thread, key, value)
            
            if self.db:
                await self._persist_plot_thread(thread)
    
    async def resolve_plot_thread(self, thread_id: str, resolved_chapter: int):
        """Mark a plot thread as resolved."""
        await self.update_plot_thread(thread_id, {
            "status": "resolved",
            "resolved_chapter": resolved_chapter
        })
    
    async def get_open_plot_threads(self) -> List[PlotThread]:
        """Get all open (unresolved) plot threads."""
        return [t for t in self._plot_threads.values() if t.status == "open"]
    
    async def get_plot_threads_by_importance(self, min_importance: str = "medium") -> List[PlotThread]:
        """Get plot threads filtered by importance."""
        importance_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_level = importance_order.get(min_importance, 1)
        
        return [
            t for t in self._plot_threads.values()
            if importance_order.get(t.importance, 1) >= min_level and t.status == "open"
        ]
    
    async def get_forgotten_threads(self, chapters_since: int = 5, current_chapter: int = 0) -> List[PlotThread]:
        """Get threads that haven't been addressed in a while."""
        forgotten = []
        for thread in self._plot_threads.values():
            if thread.status != "open":
                continue
            if thread.introduced_chapter and current_chapter - thread.introduced_chapter >= chapters_since:
                forgotten.append(thread)
        return forgotten
    
    # ==================== General Memory ====================
    
    async def store(self, 
                   memory_type: str, 
                   content: Dict[str, Any], 
                   importance: float = 0.5,
                   metadata: Dict[str, Any] = None) -> str:
        """Store a memory item."""
        import uuid
        memory_id = f"mem_{uuid.uuid4().hex[:8]}"
        
        item = MemoryItem(
            id=memory_id,
            type=memory_type,
            content=content,
            importance=importance,
            metadata=metadata or {}
        )
        
        self._memories[memory_id] = item
        
        if self.db:
            await self._persist_memory(item)
        
        return memory_id
    
    async def recall(self, memory_type: str = None, limit: int = 10) -> List[MemoryItem]:
        """
        Recall memories, optionally filtered by type.
        Returns most important/recent memories.
        """
        memories = list(self._memories.values())
        
        if memory_type:
            memories = [m for m in memories if m.type == memory_type]
        
        # Sort by importance and recency
        memories.sort(key=lambda m: (m.importance, m.access_count), reverse=True)
        
        # Update access counts
        for m in memories[:limit]:
            m.access_count += 1
            m.last_accessed = datetime.now()
        
        return memories[:limit]
    
    async def recall_by_content(self, query: str, memory_type: str = None) -> List[MemoryItem]:
        """Recall memories matching a query (simple keyword matching)."""
        results = []
        query_lower = query.lower()
        
        for memory in self._memories.values():
            if memory_type and memory.type != memory_type:
                continue
            
            content_str = json.dumps(memory.content, ensure_ascii=False).lower()
            if query_lower in content_str:
                results.append(memory)
                memory.access_count += 1
                memory.last_accessed = datetime.now()
        
        return results
    
    async def forget(self, memory_id: str):
        """Remove a memory."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            
            if self.db:
                await self._delete_memory(memory_id)
    
    # ==================== Persistence ====================
    
    async def load_from_database(self):
        """Load all memories from database."""
        if not self.db:
            return
        
        try:
            from sqlalchemy import text
            
            # Load preferences
            result = await self.db.execute(
                text("""
                    SELECT key, value FROM agent_preferences 
                    WHERE user_id = :user_id OR user_id IS NULL
                """),
                {"user_id": self.user_id}
            )
            for row in result.fetchall():
                self._preferences[row.key] = json.loads(row.value)
            
            # Load plot threads
            result = await self.db.execute(
                text("""
                    SELECT * FROM plot_threads 
                    WHERE series_id = :series_id
                """),
                {"series_id": self.series_id}
            )
            for row in result.fetchall():
                self._plot_threads[row.id] = PlotThread(
                    id=row.id,
                    title=row.title,
                    description=row.description,
                    status=row.status,
                    introduced_chapter=row.introduced_chapter,
                    resolved_chapter=row.resolved_chapter,
                    related_characters=json.loads(row.related_characters) if row.related_characters else [],
                    importance=row.importance,
                    notes=json.loads(row.notes) if row.notes else []
                )
            
            logger.info(f"Loaded {len(self._preferences)} preferences and {len(self._plot_threads)} plot threads")
            
        except Exception as e:
            logger.warning(f"Failed to load from database: {e}")
    
    async def _persist_preference(self, category: str, key: str, value: Any):
        """Persist a preference to database."""
        if not self.db:
            return
        
        try:
            from sqlalchemy import text
            await self.db.execute(
                text("""
                    INSERT INTO agent_preferences (user_id, key, value, category, updated_at)
                    VALUES (:user_id, :key, :value, :category, NOW())
                    ON CONFLICT (user_id, key) DO UPDATE SET value = :value, updated_at = NOW()
                """),
                {
                    "user_id": self.user_id,
                    "key": f"{category}.{key}",
                    "value": json.dumps(value),
                    "category": category
                }
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist preference: {e}")
    
    async def _persist_plot_thread(self, thread: PlotThread):
        """Persist a plot thread to database."""
        if not self.db:
            return
        
        try:
            from sqlalchemy import text
            await self.db.execute(
                text("""
                    INSERT INTO plot_threads (id, series_id, title, description, status, 
                        introduced_chapter, resolved_chapter, related_characters, importance, notes)
                    VALUES (:id, :series_id, :title, :description, :status, 
                        :introduced_chapter, :resolved_chapter, :related_characters, :importance, :notes)
                    ON CONFLICT (id) DO UPDATE SET 
                        title = :title, description = :description, status = :status,
                        resolved_chapter = :resolved_chapter, notes = :notes
                """),
                {
                    "id": thread.id,
                    "series_id": self.series_id,
                    "title": thread.title,
                    "description": thread.description,
                    "status": thread.status,
                    "introduced_chapter": thread.introduced_chapter,
                    "resolved_chapter": thread.resolved_chapter,
                    "related_characters": json.dumps(thread.related_characters),
                    "importance": thread.importance,
                    "notes": json.dumps(thread.notes)
                }
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist plot thread: {e}")
    
    async def _persist_feedback(self, feedback: Dict[str, Any]):
        """Persist feedback to database."""
        if not self.db:
            return
        
        try:
            from sqlalchemy import text
            await self.db.execute(
                text("""
                    INSERT INTO agent_feedback (id, user_id, series_id, task_type, 
                        content_preview, feedback, details)
                    VALUES (:id, :user_id, :series_id, :task_type, :content, :feedback, :details)
                """),
                {
                    "id": feedback["id"],
                    "user_id": self.user_id,
                    "series_id": self.series_id,
                    "task_type": feedback["task_type"],
                    "content": feedback["content_preview"],
                    "feedback": feedback["feedback"],
                    "details": json.dumps(feedback["details"])
                }
            )
            await self.db.commit()
        except Exception as e:
            logger.error(f"Failed to persist feedback: {e}")
    
    async def _persist_memory(self, item: MemoryItem):
        """Persist a memory item to database."""
        pass  # TODO: Implement if needed
    
    async def _delete_memory(self, memory_id: str):
        """Delete a memory from database."""
        pass  # TODO: Implement if needed
    
    # ==================== Summary ====================
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the memory state."""
        return {
            "total_memories": len(self._memories),
            "total_preferences": len(self._preferences),
            "total_plot_threads": len(self._plot_threads),
            "open_plot_threads": len([t for t in self._plot_threads.values() if t.status == "open"]),
            "feedback_count": len(self._feedback_history),
            "memory_types": list(set(m.type for m in self._memories.values()))
        }
