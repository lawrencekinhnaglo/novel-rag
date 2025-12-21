"""LLM Service supporting LM Studio and DeepSeek API."""
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from openai import AsyncOpenAI
from app.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMProvider:
    """Base LLM provider interface."""
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 2048) -> str:
        """Generate a response from the LLM."""
        raise NotImplementedError
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM."""
        raise NotImplementedError


class LMStudioProvider(LLMProvider):
    """LM Studio local LLM provider."""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.LM_STUDIO_URL,
            api_key="lm-studio"  # LM Studio doesn't require a real API key
        )
        self.model = settings.LM_STUDIO_MODEL
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 2048) -> str:
        """Generate a response from LM Studio."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LM Studio error: {e}")
            raise
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Stream a response from LM Studio."""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"LM Studio streaming error: {e}")
            raise


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider."""
    
    def __init__(self):
        if not settings.DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY not configured")
        self.client = AsyncOpenAI(
            base_url=settings.DEEPSEEK_API_URL,
            api_key=settings.DEEPSEEK_API_KEY
        )
        self.model = settings.DEEPSEEK_MODEL
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 2048) -> str:
        """Generate a response from DeepSeek."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek error: {e}")
            raise
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Stream a response from DeepSeek."""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"DeepSeek streaming error: {e}")
            raise


class LLMService:
    """Unified LLM service that can switch between providers."""
    
    def __init__(self, provider: str = None):
        self.provider_name = provider or settings.DEFAULT_LLM_PROVIDER
        self._provider: Optional[LLMProvider] = None
    
    @property
    def provider(self) -> LLMProvider:
        """Get or create the LLM provider."""
        if self._provider is None:
            self._provider = self._create_provider()
        return self._provider
    
    def _create_provider(self) -> LLMProvider:
        """Create the appropriate LLM provider."""
        if self.provider_name == "lm_studio":
            return LMStudioProvider()
        elif self.provider_name == "deepseek":
            return DeepSeekProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider_name}")
    
    def switch_provider(self, provider: str):
        """Switch to a different LLM provider."""
        self.provider_name = provider
        self._provider = None
    
    async def generate(self, messages: List[Dict[str, str]], 
                      temperature: float = 0.7,
                      max_tokens: int = 2048) -> str:
        """Generate a response."""
        return await self.provider.generate(messages, temperature, max_tokens)
    
    async def stream(self, messages: List[Dict[str, str]],
                    temperature: float = 0.7,
                    max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Stream a response."""
        async for chunk in self.provider.stream(messages, temperature, max_tokens):
            yield chunk
    
    async def generate_with_context(self, user_message: str,
                                    context: Dict[str, Any],
                                    system_prompt: str = None,
                                    conversation_history: List[Dict[str, str]] = None,
                                    temperature: float = 0.7) -> str:
        """Generate a response with RAG context."""
        # Build system prompt with context
        if system_prompt is None:
            system_prompt = self._build_novel_system_prompt()
        
        # Add context to system prompt
        if context:
            context_text = self._format_context(context)
            system_prompt += f"\n\n## Retrieved Context:\n{context_text}"
        
        # Build messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history[-10:])  # Last 10 messages
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        return await self.generate(messages, temperature)
    
    def _build_novel_system_prompt(self) -> str:
        """Build the default system prompt for novel writing."""
        return """You are an expert novel writing assistant with deep knowledge of storytelling, character development, plot structure, and creative writing.

Your capabilities include:
- Discussing plot ideas, character arcs, and story structure
- Providing feedback on writing samples
- Helping maintain consistency in your novel's world-building
- Suggesting improvements and alternatives
- Remembering context from previous chapters and conversations

You have access to:
- Past chapters and content from the novel
- Character profiles, relationships, and timelines
- Previously saved ideas and knowledge base entries
- Web search results when relevant

Always maintain consistency with established characters, settings, and plot points from the retrieved context.
Be creative but grounded in the existing story world."""
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary into readable text."""
        parts = []
        
        if context.get("chapters"):
            parts.append("### Relevant Chapters:")
            for ch in context["chapters"]:
                parts.append(f"- Chapter {ch.get('number', 'N/A')}: {ch.get('title', 'Untitled')}")
                if ch.get("content"):
                    parts.append(f"  {ch['content'][:500]}...")
        
        if context.get("characters"):
            parts.append("\n### Characters:")
            for char in context["characters"]:
                parts.append(f"- {char.get('name', 'Unknown')}: {char.get('description', '')}")
                if char.get("relationships"):
                    rels = ", ".join([f"{r['type']} {r['target']}" for r in char["relationships"]])
                    parts.append(f"  Relationships: {rels}")
        
        if context.get("events"):
            parts.append("\n### Timeline Events:")
            for event in context["events"]:
                parts.append(f"- {event.get('title', 'Event')}: {event.get('description', '')}")
        
        if context.get("knowledge"):
            parts.append("\n### Knowledge Base:")
            for kb in context["knowledge"]:
                parts.append(f"- {kb.get('title', 'Note')}: {kb.get('content', '')[:300]}")
        
        if context.get("web_search"):
            parts.append("\n### Web Search Results:")
            for result in context["web_search"]:
                parts.append(f"- {result.get('title', 'Result')}: {result.get('snippet', '')}")
        
        return "\n".join(parts) if parts else "No additional context available."


def get_llm_service(provider: str = None) -> LLMService:
    """Get LLM service instance."""
    return LLMService(provider)

