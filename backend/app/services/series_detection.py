"""Series Detection Service - Automatically detects which series/book a message belongs to."""
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from sqlalchemy import text

from app.database.postgres import AsyncSessionLocal
from app.services.embeddings import generate_embedding
from app.database.qdrant_client import get_vector_manager
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SeriesMatch:
    """Result of series detection."""
    series_id: Optional[int]
    series_title: Optional[str]
    confidence: float  # 0.0 to 1.0
    matched_elements: List[str]  # What triggered the match (character names, concepts, etc.)
    is_new_series_request: bool  # User wants to create a new series
    suggested_series_name: Optional[str]  # If new series, what to call it


class SeriesDetectionService:
    """
    Service for automatically detecting which series a message belongs to.
    
    Uses multiple strategies:
    1. Keyword matching (character names, concepts, locations)
    2. Semantic similarity (embedding comparison with series content)
    3. Intent detection (is user asking to create new series?)
    """
    
    def __init__(self):
        self.min_confidence_threshold = 0.3
    
    async def detect_series(
        self, 
        message: str, 
        current_series_id: Optional[int] = None,
        session_history: List[Dict[str, str]] = None
    ) -> SeriesMatch:
        """
        Detect which series a message belongs to.
        
        Args:
            message: The user's message
            current_series_id: Currently selected series (if any)
            session_history: Previous messages in the session for context
        
        Returns:
            SeriesMatch with the detected series or new series suggestion
        """
        # Check if user is asking to create a new series
        if self._is_new_series_request(message):
            suggested_name = self._extract_series_name(message)
            return SeriesMatch(
                series_id=None,
                series_title=None,
                confidence=0.9,
                matched_elements=["new_series_request"],
                is_new_series_request=True,
                suggested_series_name=suggested_name
            )
        
        # Get all series and their key elements
        series_data = await self._get_series_with_elements()
        
        if not series_data:
            return SeriesMatch(
                series_id=None,
                series_title=None,
                confidence=0.0,
                matched_elements=[],
                is_new_series_request=False,
                suggested_series_name=None
            )
        
        # Strategy 1: Keyword matching
        keyword_matches = await self._keyword_match(message, series_data)
        
        # Strategy 2: Semantic similarity
        semantic_matches = await self._semantic_match(message, series_data)
        
        # Combine results
        best_match = self._combine_matches(keyword_matches, semantic_matches, current_series_id)
        
        return best_match
    
    def _is_new_series_request(self, message: str) -> bool:
        """Check if the user is asking to create a new series/story."""
        new_series_keywords = [
            "新故事", "新系列", "新小說", "開始新的", "創建新",
            "new story", "new series", "new novel", "start a new", "create a new",
            "想寫一個新的", "我要開始寫", "我在構思一個新",
            "let me start a new", "i want to create", "let's begin a new"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in new_series_keywords)
    
    def _extract_series_name(self, message: str) -> Optional[str]:
        """Try to extract a series name from the message."""
        # Look for quoted text or specific patterns
        import re
        
        # Pattern: "called X", "named X", "叫做X"
        patterns = [
            r'(?:called|named|titled)\s*["\']?([^"\']+)["\']?',
            r'(?:叫做|名為|名字是)\s*[「『"\'"]?([^」』"\'"]+)[」』"\'""]?',
            r'[「『"\'"]([^」』"\'"]+)[」』"\'""]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    async def _get_series_with_elements(self) -> List[Dict[str, Any]]:
        """Get all series with their key elements (characters, concepts, etc.)."""
        series_data = []
        
        try:
            async with AsyncSessionLocal() as db:
                # Get all series
                series_result = await db.execute(
                    text("SELECT id, title, premise, themes FROM series ORDER BY id")
                )
                series_rows = series_result.fetchall()
                
                for series in series_rows:
                    series_info = {
                        "id": series.id,
                        "title": series.title,
                        "premise": series.premise or "",
                        "themes": series.themes or [],
                        "characters": [],
                        "concepts": [],
                        "keywords": set()
                    }
                    
                    # Get characters for this series
                    chars_result = await db.execute(
                        text("""
                            SELECT name, aliases FROM character_profiles 
                            WHERE series_id = :series_id
                        """),
                        {"series_id": series.id}
                    )
                    for char in chars_result.fetchall():
                        series_info["characters"].append(char.name)
                        series_info["keywords"].add(char.name.lower())
                        if char.aliases:
                            for alias in char.aliases:
                                series_info["keywords"].add(alias.lower())
                    
                    # Get world rules
                    rules_result = await db.execute(
                        text("""
                            SELECT rule_name FROM world_rules 
                            WHERE series_id = :series_id
                        """),
                        {"series_id": series.id}
                    )
                    for rule in rules_result.fetchall():
                        if rule.rule_name:
                            series_info["concepts"].append(rule.rule_name)
                            series_info["keywords"].add(rule.rule_name.lower())
                    
                    # Get knowledge base concepts
                    kb_result = await db.execute(
                        text("""
                            SELECT title FROM knowledge_base 
                            WHERE :series_tag = ANY(tags)
                            LIMIT 50
                        """),
                        {"series_tag": f"series:{series.id}"}
                    )
                    for kb in kb_result.fetchall():
                        if kb.title:
                            series_info["keywords"].add(kb.title.lower())
                    
                    # Add series title as keyword
                    series_info["keywords"].add(series.title.lower())
                    
                    series_data.append(series_info)
                    
        except Exception as e:
            logger.error(f"Failed to get series data: {e}")
        
        return series_data
    
    async def _keyword_match(
        self, 
        message: str, 
        series_data: List[Dict[str, Any]]
    ) -> Dict[int, Tuple[float, List[str]]]:
        """
        Match message against series keywords.
        Returns: {series_id: (confidence, matched_elements)}
        """
        matches = {}
        message_lower = message.lower()
        
        for series in series_data:
            matched_elements = []
            
            # Check title
            if series["title"].lower() in message_lower:
                matched_elements.append(f"title:{series['title']}")
            
            # Check characters
            for char in series["characters"]:
                if char.lower() in message_lower:
                    matched_elements.append(f"character:{char}")
            
            # Check concepts
            for concept in series["concepts"]:
                if concept.lower() in message_lower:
                    matched_elements.append(f"concept:{concept}")
            
            # Check keywords
            for keyword in series["keywords"]:
                if len(keyword) > 2 and keyword in message_lower:  # Skip very short keywords
                    if not any(keyword in elem for elem in matched_elements):
                        matched_elements.append(f"keyword:{keyword}")
            
            if matched_elements:
                # Calculate confidence based on number of matches
                confidence = min(0.3 + (len(matched_elements) * 0.15), 0.95)
                matches[series["id"]] = (confidence, matched_elements)
        
        return matches
    
    async def _semantic_match(
        self, 
        message: str, 
        series_data: List[Dict[str, Any]]
    ) -> Dict[int, Tuple[float, List[str]]]:
        """
        Match message against series content using semantic similarity.
        Returns: {series_id: (confidence, matched_elements)}
        """
        matches = {}
        
        try:
            # Generate embedding for the message
            message_embedding = generate_embedding(message)
            vector_manager = get_vector_manager()
            
            # Search in knowledge base with series tags
            results = vector_manager.search(
                collection="knowledge_base",
                query_vector=message_embedding,
                limit=10,
                score_threshold=0.5
            )
            
            # Group results by series
            series_scores = {}
            for result in results:
                payload = result.get("payload", {})
                tags = payload.get("tags", [])
                score = result.get("score", 0)
                
                for tag in tags:
                    if tag.startswith("series:"):
                        try:
                            sid = int(tag.split(":")[1])
                            if sid not in series_scores:
                                series_scores[sid] = []
                            series_scores[sid].append((score, payload.get("title", "content")))
                        except:
                            pass
            
            # Convert to confidence scores
            for sid, scores in series_scores.items():
                avg_score = sum(s[0] for s in scores) / len(scores)
                confidence = min(avg_score * 0.8, 0.9)  # Cap at 0.9
                matched = [f"semantic:{s[1]}" for s in scores[:3]]
                matches[sid] = (confidence, matched)
                
        except Exception as e:
            logger.warning(f"Semantic matching failed: {e}")
        
        return matches
    
    def _combine_matches(
        self,
        keyword_matches: Dict[int, Tuple[float, List[str]]],
        semantic_matches: Dict[int, Tuple[float, List[str]]],
        current_series_id: Optional[int]
    ) -> SeriesMatch:
        """Combine keyword and semantic matches to determine the best match."""
        
        all_series_ids = set(keyword_matches.keys()) | set(semantic_matches.keys())
        
        if not all_series_ids:
            return SeriesMatch(
                series_id=None,
                series_title=None,
                confidence=0.0,
                matched_elements=[],
                is_new_series_request=False,
                suggested_series_name=None
            )
        
        # Calculate combined scores
        combined_scores = {}
        for sid in all_series_ids:
            kw_conf, kw_elems = keyword_matches.get(sid, (0.0, []))
            sem_conf, sem_elems = semantic_matches.get(sid, (0.0, []))
            
            # Weight keyword matches slightly higher
            combined_conf = (kw_conf * 0.6) + (sem_conf * 0.4)
            
            # Boost current series slightly
            if sid == current_series_id:
                combined_conf = min(combined_conf + 0.1, 1.0)
            
            combined_scores[sid] = (combined_conf, kw_elems + sem_elems)
        
        # Find best match
        best_sid = max(combined_scores.keys(), key=lambda x: combined_scores[x][0])
        best_conf, best_elems = combined_scores[best_sid]
        
        # Get series title
        series_title = None
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            # We can't easily do async here, so we'll return the ID and let caller resolve
        except:
            pass
        
        return SeriesMatch(
            series_id=best_sid if best_conf >= self.min_confidence_threshold else None,
            series_title=series_title,
            confidence=best_conf,
            matched_elements=best_elems[:5],  # Top 5 matches
            is_new_series_request=False,
            suggested_series_name=None
        )
    
    async def get_series_suggestions(self, message: str) -> List[Dict[str, Any]]:
        """
        Get a list of possible series matches with confidence scores.
        Useful for showing the user options when detection is ambiguous.
        """
        series_data = await self._get_series_with_elements()
        keyword_matches = await self._keyword_match(message, series_data)
        semantic_matches = await self._semantic_match(message, series_data)
        
        suggestions = []
        all_series_ids = set(keyword_matches.keys()) | set(semantic_matches.keys())
        
        for sid in all_series_ids:
            kw_conf, kw_elems = keyword_matches.get(sid, (0.0, []))
            sem_conf, sem_elems = semantic_matches.get(sid, (0.0, []))
            combined_conf = (kw_conf * 0.6) + (sem_conf * 0.4)
            
            # Find series title
            series = next((s for s in series_data if s["id"] == sid), None)
            if series:
                suggestions.append({
                    "series_id": sid,
                    "title": series["title"],
                    "confidence": combined_conf,
                    "matched_elements": (kw_elems + sem_elems)[:5]
                })
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions


def get_series_detection_service() -> SeriesDetectionService:
    """Get series detection service instance."""
    return SeriesDetectionService()


