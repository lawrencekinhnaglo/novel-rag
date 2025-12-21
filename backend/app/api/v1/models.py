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


class ChatRequest(BaseModel):
    session_id: Optional[UUID] = Field(None, description="Chat session ID")
    message: str = Field(..., description="User message")
    use_rag: bool = Field(True, description="Whether to use RAG for context")
    use_web_search: bool = Field(False, description="Whether to search the web")
    provider: Optional[str] = Field(None, description="LLM provider: 'lm_studio' or 'deepseek'")
    temperature: float = Field(0.7, ge=0, le=2)
    include_graph: bool = Field(True, description="Include graph context")
    language: str = Field("en", description="Language: 'en', 'zh-TW', 'zh-CN'")
    uploaded_content: Optional[str] = Field(None, description="Content from uploaded document")
    categories: Optional[List[str]] = Field(None, description="Knowledge categories to search")


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
    language: str = Field("en", description="Language: 'en', 'zh-TW', 'zh-CN'")
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

