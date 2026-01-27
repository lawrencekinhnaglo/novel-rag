"""
Writing Assistant API - Conversational co-writer endpoints.

Flow:
1. POST /writing/session - Start a writing session
2. POST /writing/discuss - Chat about the chapter
3. POST /writing/write - Generate chapter content
4. POST /writing/refine - Refine the draft
5. POST /writing/save - Save the chapter
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from app.database.postgres import get_db
from app.services.writing_assistant import get_writing_assistant, WritingSession
from app.services.llm_service import get_llm_service
from app.services.rag_service import get_rag_service

router = APIRouter(prefix="/writing", tags=["writing"])
logger = logging.getLogger(__name__)


# ==================== Request/Response Models ====================

class StartSessionRequest(BaseModel):
    series_id: Optional[int] = None
    book_id: Optional[int] = None
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None


class StartSessionResponse(BaseModel):
    session_id: str
    message: str


class DiscussRequest(BaseModel):
    session_id: str
    message: str


class DiscussResponse(BaseModel):
    response: str
    session_id: str


class WriteRequest(BaseModel):
    session_id: str
    additional_instructions: Optional[str] = None


class WriteResponse(BaseModel):
    content: str
    word_count: int
    session_id: str


class RefineRequest(BaseModel):
    session_id: str
    instruction: str


class QuickRefineRequest(BaseModel):
    session_id: str
    action: str  # longer, shorter, more_dialogue, more_action, more_emotion


class SaveRequest(BaseModel):
    session_id: str
    title: Optional[str] = None


class SaveResponse(BaseModel):
    success: bool
    chapter_id: Optional[int] = None
    title: Optional[str] = None
    word_count: Optional[int] = None
    error: Optional[str] = None


class SessionStatusResponse(BaseModel):
    session_id: str
    has_draft: bool
    draft_count: int
    discussion_count: int
    chapter_info: Dict[str, Any]


# ==================== Endpoints ====================

@router.post("/session", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new writing session.
    
    This creates a context for discussing and writing a chapter.
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    session = assistant.start_session(
        series_id=request.series_id,
        book_id=request.book_id,
        chapter_number=request.chapter_number,
        chapter_title=request.chapter_title
    )
    
    chapter_desc = ""
    if request.chapter_number:
        chapter_desc = f"第{request.chapter_number}章"
    if request.chapter_title:
        chapter_desc += f" {request.chapter_title}"
    
    return StartSessionResponse(
        session_id=session.id,
        message=f"寫作會話已開始{' - ' + chapter_desc if chapter_desc else ''}。讓我們聊聊你想寫什麼？"
    )


@router.post("/discuss", response_model=DiscussResponse)
async def discuss(
    request: DiscussRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Discuss the chapter with the AI.
    
    Talk about what you want:
    - Plot points
    - Character interactions
    - Mood and tone
    - Specific scenes
    
    The AI will ask clarifying questions and suggest ideas.
    When ready, say "開始寫" or "write" to generate content.
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    response = await assistant.discuss(request.session_id, request.message)
    
    return DiscussResponse(
        response=response,
        session_id=request.session_id
    )


@router.post("/write", response_model=WriteResponse)
async def write_chapter(
    request: WriteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate chapter content based on discussion + knowledge base.
    
    This is where the magic happens - AI writes while you relax!
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    content = await assistant.write_chapter(
        request.session_id,
        request.additional_instructions
    )
    
    return WriteResponse(
        content=content,
        word_count=len(content),
        session_id=request.session_id
    )


@router.post("/refine", response_model=WriteResponse)
async def refine_draft(
    request: RefineRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refine the current draft.
    
    Examples:
    - "打鬥場面寫長一點"
    - "加入更多對話"
    - "結尾改成懸念"
    - "把主角的心理描寫加深"
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    content = await assistant.refine(request.session_id, request.instruction)
    
    return WriteResponse(
        content=content,
        word_count=len(content),
        session_id=request.session_id
    )


@router.post("/quick-refine", response_model=WriteResponse)
async def quick_refine(
    request: QuickRefineRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Quick refinement actions.
    
    Actions:
    - "longer" - Make it longer
    - "shorter" - Make it shorter
    - "more_dialogue" - Add more dialogue
    - "more_action" - Add more action
    - "more_emotion" - Deepen emotional content
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    content = await assistant.quick_refine(request.session_id, request.action)
    
    return WriteResponse(
        content=content,
        word_count=len(content),
        session_id=request.session_id
    )


@router.post("/save", response_model=SaveResponse)
async def save_chapter(
    request: SaveRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Save the current draft as a chapter.
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    result = await assistant.save_chapter(request.session_id, request.title)
    
    return SaveResponse(
        success=result.get("success", False),
        chapter_id=result.get("chapter_id"),
        title=result.get("title"),
        word_count=result.get("word_count"),
        error=result.get("error")
    )


@router.get("/session/{session_id}", response_model=SessionStatusResponse)
async def get_session_status(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the status of a writing session.
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    session = assistant.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionStatusResponse(
        session_id=session.id,
        has_draft=bool(session.current_draft),
        draft_count=len(session.drafts),
        discussion_count=len(session.discussion),
        chapter_info={
            "series_id": session.series_id,
            "book_id": session.book_id,
            "chapter_number": session.chapter_number,
            "chapter_title": session.chapter_title
        }
    )


@router.get("/session/{session_id}/discussion")
async def get_discussion_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the discussion history for a session.
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    session = assistant.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.id,
        "messages": [m.to_dict() for m in session.discussion]
    }


@router.get("/session/{session_id}/draft")
async def get_current_draft(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current draft for a session.
    """
    llm_service = get_llm_service()
    rag_service = get_rag_service()
    assistant = get_writing_assistant(llm_service, rag_service, db)
    
    session = assistant.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.id,
        "content": session.current_draft,
        "word_count": len(session.current_draft) if session.current_draft else 0,
        "version": len(session.drafts)
    }
