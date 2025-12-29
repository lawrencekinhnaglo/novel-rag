"""Pydantic models for API requests and responses."""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID


# Chat Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message content")
    metadata: Optional[Dict[str, Any]] = Field(default={})


class LikedQAPairInput(BaseModel):
    user_question: str
    assistant_response: str


class ChatRequest(BaseModel):
    session_id: Optional[UUID] = Field(None, description="Chat session ID")
    message: str = Field(..., description="User message")
    use_rag: bool = Field(True, description="Whether to use RAG for context")
    use_web_search: bool = Field(False, description="Whether to search the web")
    provider: Optional[str] = Field(None, description="LLM provider: 'lm_studio', 'deepseek', or 'ollama'")
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(8192, ge=100, le=32000, description="Maximum tokens for response (default 8192)")
    include_graph: bool = Field(True, description="Include graph context")
    language: str = Field("en", description="Language: 'en', 'zh-TW', 'zh-CN'")
    uploaded_content: Optional[str] = Field(None, description="Content from uploaded document")
    categories: Optional[List[str]] = Field(None, description="Knowledge categories to search")
    # Story position context (Improvement #4)
    series_id: Optional[int] = Field(None, description="Series ID for position-aware prompts")
    book_id: Optional[int] = Field(None, description="Current book ID")
    chapter_number: Optional[int] = Field(None, description="Current chapter number")
    # Liked Q&A pairs for context (auto-cached from liked responses)
    liked_context: Optional[List[LikedQAPairInput]] = Field(None, description="Previously liked Q&A pairs to use as context")


class ChatResponse(BaseModel):
    session_id: UUID
    message: str
    context_used: Optional[Dict[str, Any]] = None
    sources: Optional[List[Dict[str, Any]]] = None


# Session Models
class SessionCreate(BaseModel):
    title: Optional[str] = Field("New Chat", description="Session title")


class SessionUpdate(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    total: int


# Knowledge Base Models
class KnowledgeCreate(BaseModel):
    source_type: str = Field(..., description="Type: 'chat', 'document', 'idea', 'upload'")
    category: str = Field("other", description="Category: draft, concept, character, chapter, settings, worldbuilding, plot, dialogue, research, other")
    title: Optional[str] = None
    content: str = Field(..., description="Knowledge content")
    language: str = Field("en", description="Language: 'en', 'zh-TW', 'zh-CN'")
    tags: Optional[List[str]] = Field(default=[])
    metadata: Optional[Dict[str, Any]] = Field(default={})


class KnowledgeResponse(BaseModel):
    id: int
    source_type: str
    category: str
    title: Optional[str]
    content: str
    language: str
    tags: List[str]
    created_at: datetime


class SaveChatAsKnowledge(BaseModel):
    session_id: UUID
    title: Optional[str] = None
    category: str = Field("other", description="Knowledge category")
    language: str = Field("en", description="Language")
    tags: Optional[List[str]] = Field(default=[])


# Chapter Models
class ChapterCreate(BaseModel):
    title: str
    content: str
    chapter_number: Optional[int] = None
    book_id: Optional[int] = Field(None, description="Book this chapter belongs to")
    series_id: Optional[int] = Field(None, description="Series for auto-analysis")
    pov_character: Optional[str] = Field(None, description="Point of view character")
    language: str = Field("en", description="Language: 'en', 'zh-TW', 'zh-CN'")
    auto_analyze: bool = Field(True, description="Run automatic LLM analysis on save")
    metadata: Optional[Dict[str, Any]] = Field(default={})


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    chapter_number: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ChapterResponse(BaseModel):
    id: int
    title: str
    content: str
    chapter_number: Optional[int]
    word_count: int
    created_at: datetime
    updated_at: datetime


# Idea Models
class IdeaCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = Field(default=[])
    related_chapters: Optional[List[int]] = Field(default=[])


class IdeaResponse(BaseModel):
    id: int
    title: str
    content: str
    category: Optional[str]
    tags: List[str]
    related_chapters: List[int]
    created_at: datetime


# Graph Models
class CharacterCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    attributes: Optional[Dict[str, Any]] = Field(default={})


class RelationshipCreate(BaseModel):
    character1: str
    character2: str
    relationship_type: str
    properties: Optional[Dict[str, Any]] = Field(default={})


class LocationCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    attributes: Optional[Dict[str, Any]] = Field(default={})


class EventCreate(BaseModel):
    event_id: str
    title: str
    description: str
    timestamp: Optional[str] = None
    chapter: Optional[int] = None
    characters: Optional[List[str]] = Field(default=[])
    location: Optional[str] = None


# Search Models
class SearchRequest(BaseModel):
    query: str
    collections: Optional[List[str]] = Field(default=["chapters", "knowledge", "ideas"])
    limit: int = Field(5, ge=1, le=20)
    include_graph: bool = Field(True)


class SearchResponse(BaseModel):
    query: str
    results: Dict[str, List[Dict[str, Any]]]
    total_results: int


class WebSearchRequest(BaseModel):
    query: str
    search_type: str = Field("text", description="'text', 'news', or 'images'")
    max_results: int = Field(5, ge=1, le=10)


class WebSearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    search_type: str


# Feedback Models for Like/Dislike
class FeedbackCreate(BaseModel):
    session_id: UUID = Field(..., description="Chat session ID")
    user_message_id: int = Field(..., description="ID of the user's message")
    assistant_message_id: int = Field(..., description="ID of the assistant's response")
    feedback_type: str = Field(..., description="'like' or 'dislike'")


class FeedbackResponse(BaseModel):
    id: int
    session_id: UUID
    user_message_id: int
    assistant_message_id: int
    feedback_type: str
    user_question: str
    assistant_response: str
    created_at: datetime


class LikedQAPair(BaseModel):
    user_question: str
    assistant_response: str

