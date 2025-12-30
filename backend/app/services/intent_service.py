"""Intent Detection Service using Ollama Qwen3 for intelligent function routing."""
import json
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from app.config import settings
from app.services.llm_service import OllamaProvider

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Available intent types the system can handle."""
    # Chat & Discussion
    CHAT = "chat"  # General conversation about the story
    
    # Content Creation
    WRITE_CHAPTER = "write_chapter"  # Write a new chapter
    WRITE_SCENE = "write_scene"  # Write a specific scene
    CONTINUE_STORY = "continue_story"  # Continue from where the story left off
    WRITE_DIALOGUE = "write_dialogue"  # Write dialogue for characters
    
    # Story Management
    CREATE_CHARACTER = "create_character"  # Create a new character profile
    UPDATE_CHARACTER = "update_character"  # Update existing character
    CREATE_WORLD_RULE = "create_world_rule"  # Create a world-building rule
    CREATE_FORESHADOWING = "create_foreshadowing"  # Plant a foreshadowing seed
    CREATE_SERIES = "create_series"  # Create a new story series
    CREATE_BOOK = "create_book"  # Create a new book in existing series
    
    # Analysis & Query
    ANALYZE_CONSISTENCY = "analyze_consistency"  # Check for consistency issues
    QUERY_CHARACTER = "query_character"  # Ask about a character
    QUERY_PLOT = "query_plot"  # Ask about plot/story structure
    QUERY_TIMELINE = "query_timeline"  # Ask about timeline/events
    ANALYZE_FORESHADOWING = "analyze_foreshadowing"  # Analyze foreshadowing payoffs
    
    # Knowledge Management
    SAVE_TO_KNOWLEDGE = "save_to_knowledge"  # Save content to knowledge base
    SEARCH_KNOWLEDGE = "search_knowledge"  # Search the knowledge base
    
    # Document Operations
    SUMMARIZE = "summarize"  # Summarize content
    EXTRACT_ELEMENTS = "extract_elements"  # Extract story elements
    
    # Unknown
    UNKNOWN = "unknown"


@dataclass
class DetectedIntent:
    """Result of intent detection."""
    intent: IntentType
    confidence: float
    parameters: Dict[str, Any]
    original_message: str
    explanation: str


@dataclass  
class FunctionResult:
    """Result of function execution."""
    success: bool
    result: Any
    message: str
    should_continue_chat: bool = True  # Whether to proceed with normal chat after


class IntentService:
    """Service for detecting user intent and routing to appropriate functions."""
    
    def __init__(self):
        self.llm = OllamaProvider(model=settings.OLLAMA_INTENT_MODEL)
        self.function_handlers: Dict[IntentType, Callable[[DetectedIntent], Awaitable[FunctionResult]]] = {}
        self._register_default_handlers()
    
    def register_handler(
        self, 
        intent: IntentType, 
        handler: Callable[[DetectedIntent], Awaitable[FunctionResult]]
    ):
        """Register a function handler for an intent."""
        self.function_handlers[intent] = handler
    
    def _register_default_handlers(self):
        """Register default handlers for built-in intents."""
        # These will be called when the intent is detected
        # Most intents will have handlers registered in the chat API
        pass
    
    async def detect_intent(self, message: str, context: Dict[str, Any] = None) -> DetectedIntent:
        """
        Detect the user's intent from their message.
        Uses Ollama Qwen3 for intelligent intent classification.
        """
        # Build the intent detection prompt
        prompt = self._build_intent_prompt(message, context)
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=1024
            )
            
            # Parse the response
            return self._parse_intent_response(response, message)
            
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            # Default to chat on failure
            return DetectedIntent(
                intent=IntentType.CHAT,
                confidence=0.5,
                parameters={},
                original_message=message,
                explanation="Intent detection failed, defaulting to chat"
            )
    
    def _build_intent_prompt(self, message: str, context: Dict[str, Any] = None) -> str:
        """Build the prompt for intent detection."""
        
        intent_descriptions = """
AVAILABLE INTENTS:

1. chat - General conversation, questions, or discussion about the story
2. write_chapter - User wants to write a new chapter (keywords: "write chapter", "new chapter", "create chapter")
3. write_scene - User wants to write a specific scene (keywords: "write scene", "scene where", "write a scene")
4. continue_story - User wants to continue the story from where it left off (keywords: "continue", "what happens next", "keep writing")
5. write_dialogue - User wants dialogue written (keywords: "dialogue between", "conversation between", "what would X say")
6. create_character - User wants to create a new character (keywords: "create character", "new character", "add character")
7. update_character - User wants to modify an existing character (keywords: "update character", "change character", "modify character")
8. create_world_rule - User wants to add a world-building rule (keywords: "world rule", "add rule", "establish rule", "world setting")
9. create_foreshadowing - User wants to plant foreshadowing (keywords: "foreshadow", "hint at", "plant seed", "setup for later")
10. analyze_consistency - User wants to check for plot holes or inconsistencies (keywords: "check consistency", "plot holes", "inconsistencies")
11. query_character - User is asking about a character's traits, history, or behavior (keywords: "who is", "what does X think", "X's personality")
12. query_plot - User is asking about plot structure or story arc (keywords: "what's the plot", "story structure", "what happens in")
13. query_timeline - User is asking about events or timeline (keywords: "when did", "timeline", "order of events")
14. analyze_foreshadowing - User wants to analyze foreshadowing payoffs (keywords: "foreshadowing status", "payoff", "unresolved hints")
15. save_to_knowledge - User wants to save something to knowledge base (keywords: "save this", "remember this", "add to knowledge")
16. search_knowledge - User wants to search the knowledge base (keywords: "search for", "find", "look up")
17. summarize - User wants content summarized (keywords: "summarize", "summary of", "brief overview")
18. extract_elements - User wants to extract story elements from text (keywords: "extract", "identify elements", "find characters/rules/etc")
"""

        context_info = ""
        if context:
            if context.get("current_chapter"):
                context_info += f"\nCurrent chapter: {context['current_chapter']}"
            if context.get("recent_topics"):
                context_info += f"\nRecent topics: {', '.join(context['recent_topics'])}"
        
        return f"""/no_think
You are an intent classification system for a novel writing assistant.
Analyze the user's message and determine their intent.

{intent_descriptions}

USER MESSAGE: "{message}"
{context_info}

Respond with a JSON object containing:
- "intent": one of the intent types listed above (lowercase)
- "confidence": a number between 0 and 1 indicating how confident you are
- "parameters": an object with extracted parameters relevant to the intent:
  - For write_chapter/scene: {{"chapter_number": int, "title": str, "characters": [str], "setting": str, "mood": str}}
  - For create_character: {{"name": str, "description": str, "role": str}}
  - For create_world_rule: {{"rule": str, "category": str}}
  - For create_foreshadowing: {{"seed_type": str, "content": str, "payoff_hint": str}}
  - For query_*: {{"subject": str, "specific_question": str}}
  - For others: extract any relevant info
- "explanation": brief explanation of why you chose this intent

JSON response only, no additional text:
"""
    
    def _parse_intent_response(self, response: str, original_message: str) -> DetectedIntent:
        """Parse the LLM response into a DetectedIntent."""
        try:
            # Try to extract JSON from the response
            response = response.strip()
            
            # Handle potential markdown code blocks
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()
            
            # Find JSON object in response
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)
                
                intent_str = data.get("intent", "chat").lower()
                try:
                    intent = IntentType(intent_str)
                except ValueError:
                    intent = IntentType.CHAT
                
                return DetectedIntent(
                    intent=intent,
                    confidence=float(data.get("confidence", 0.7)),
                    parameters=data.get("parameters", {}),
                    original_message=original_message,
                    explanation=data.get("explanation", "")
                )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse intent response: {e}")
        
        # Default to chat
        return DetectedIntent(
            intent=IntentType.CHAT,
            confidence=0.5,
            parameters={},
            original_message=original_message,
            explanation="Could not parse intent, defaulting to chat"
        )
    
    async def execute_intent(self, intent: DetectedIntent) -> Optional[FunctionResult]:
        """
        Execute the function associated with the detected intent.
        Returns None if no handler is registered (proceed with normal chat).
        """
        handler = self.function_handlers.get(intent.intent)
        
        if handler:
            try:
                return await handler(intent)
            except Exception as e:
                logger.error(f"Function execution failed for {intent.intent}: {e}")
                return FunctionResult(
                    success=False,
                    result=None,
                    message=f"Error executing {intent.intent}: {str(e)}",
                    should_continue_chat=True
                )
        
        return None  # No handler, proceed with normal chat
    
    async def detect_and_execute(
        self, 
        message: str, 
        context: Dict[str, Any] = None
    ) -> tuple[DetectedIntent, Optional[FunctionResult]]:
        """
        Detect intent and execute associated function in one call.
        Returns both the detected intent and the function result (if any).
        """
        intent = await self.detect_intent(message, context)
        result = await self.execute_intent(intent)
        return intent, result


# Singleton instance
_intent_service: Optional[IntentService] = None


def get_intent_service() -> IntentService:
    """Get or create the intent service singleton."""
    global _intent_service
    if _intent_service is None:
        _intent_service = IntentService()
    return _intent_service

