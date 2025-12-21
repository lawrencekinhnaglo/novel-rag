"""Web search service using DuckDuckGo."""
from typing import List, Dict, Any
from duckduckgo_search import DDGS
import logging

logger = logging.getLogger(__name__)


class WebSearchService:
    """Web search service using DuckDuckGo."""
    
    def __init__(self):
        self.ddgs = DDGS()
    
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Perform a web search and return results."""
        try:
            results = []
            for r in self.ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "duckduckgo"
                })
            return results
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return []
    
    def search_news(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search for news articles."""
        try:
            results = []
            for r in self.ddgs.news(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("body", ""),
                    "date": r.get("date", ""),
                    "source": r.get("source", ""),
                    "type": "news"
                })
            return results
        except Exception as e:
            logger.error(f"News search error: {e}")
            return []
    
    def search_images(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search for images (useful for character/setting references)."""
        try:
            results = []
            for r in self.ddgs.images(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("image", ""),
                    "thumbnail": r.get("thumbnail", ""),
                    "source": r.get("source", ""),
                    "type": "image"
                })
            return results
        except Exception as e:
            logger.error(f"Image search error: {e}")
            return []


def get_web_search_service() -> WebSearchService:
    """Get web search service instance."""
    return WebSearchService()

