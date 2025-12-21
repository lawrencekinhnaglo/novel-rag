"""Story management API endpoints - Series, Books, Foreshadowing, Analysis."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel, Field
import json

from app.database.postgres import get_db
from app.services.story_analysis import get_story_analysis_service
from app.services.embeddings import generate_embedding

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class SeriesCreate(BaseModel):
    title: str
    premise: Optional[str] = None
    themes: Optional[List[str]] = []
    total_planned_books: int = 1
    language: str = "en"

class SeriesResponse(BaseModel):
    id: int
    title: str
    premise: Optional[str]
    themes: List[str]
    total_planned_books: int
    language: str

class BookCreate(BaseModel):
    series_id: int
    book_number: int
    title: str
    theme: Optional[str] = None
    synopsis: Optional[str] = None
    target_word_count: Optional[int] = None

class BookResponse(BaseModel):
    id: int
    series_id: int
    book_number: int
    title: str
    theme: Optional[str]
    status: str
    target_word_count: Optional[int]
    current_word_count: int

class ForeshadowingCreate(BaseModel):
    series_id: int
    title: str
    planted_book: int
    planted_chapter: int
    planted_text: str
    seed_type: str = "plot"
    subtlety: int = Field(3, ge=1, le=5)
    intended_payoff: Optional[str] = None

class ForeshadowingUpdate(BaseModel):
    payoff_book: Optional[int] = None
    payoff_chapter: Optional[int] = None
    payoff_text: Optional[str] = None
    status: Optional[str] = None

class WorldRuleCreate(BaseModel):
    series_id: int
    rule_category: str
    rule_name: str
    rule_description: str
    exceptions: Optional[List[str]] = []
    source_book: Optional[int] = None
    source_chapter: Optional[int] = None
    is_hard_rule: bool = True

class CharacterKnowledgeAdd(BaseModel):
    character_name: str
    series_id: int
    fact_description: str
    fact_category: str = "plot"
    learned_in_chapter: int
    learned_how: str = "witnessed"
    certainty: str = "knows"
    is_secret: bool = False

class KnowledgeCheckRequest(BaseModel):
    character_name: str
    proposed_action: str
    current_chapter: int
    series_id: int

class KnowledgeQueryRequest(BaseModel):
    character_name: str
    question: str
    as_of_chapter: int
    series_id: int

class ConsistencyCheckRequest(BaseModel):
    content: str
    series_id: int
    check_types: Optional[List[str]] = ["world_rules", "character", "timeline"]

class ForeshadowingAnalysisRequest(BaseModel):
    chapter_content: str
    series_id: int
    current_book: int
    current_chapter: int


# ============================================================================
# SERIES ENDPOINTS
# ============================================================================

@router.post("/story/series", response_model=SeriesResponse)
async def create_series(
    series: SeriesCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new series."""
    result = await db.execute(
        text("""
            INSERT INTO series (title, premise, themes, total_planned_books, language)
            VALUES (:title, :premise, :themes, :total_books, :language)
            RETURNING id, title, premise, themes, total_planned_books, language
        """),
        {
            "title": series.title,
            "premise": series.premise,
            "themes": series.themes,
            "total_books": series.total_planned_books,
            "language": series.language
        }
    )
    await db.commit()
    row = result.fetchone()
    
    return SeriesResponse(
        id=row.id,
        title=row.title,
        premise=row.premise,
        themes=row.themes or [],
        total_planned_books=row.total_planned_books,
        language=row.language
    )


@router.get("/story/series")
async def list_series(db: AsyncSession = Depends(get_db)):
    """List all series."""
    result = await db.execute(
        text("""
            SELECT s.*, 
                   (SELECT COUNT(*) FROM books WHERE series_id = s.id) as book_count
            FROM series s
            ORDER BY s.created_at DESC
        """)
    )
    rows = result.fetchall()
    
    return {
        "series": [
            {
                "id": r.id,
                "title": r.title,
                "premise": r.premise,
                "themes": r.themes or [],
                "total_planned_books": r.total_planned_books,
                "book_count": r.book_count,
                "language": r.language
            }
            for r in rows
        ]
    }


@router.get("/story/series/{series_id}")
async def get_series(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get a series with its books."""
    series_result = await db.execute(
        text("SELECT * FROM series WHERE id = :id"),
        {"id": series_id}
    )
    series = series_result.fetchone()
    
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    
    books_result = await db.execute(
        text("""
            SELECT b.*, 
                   (SELECT COUNT(*) FROM chapters WHERE book_id = b.id) as chapter_count
            FROM books b
            WHERE b.series_id = :series_id
            ORDER BY b.book_number
        """),
        {"series_id": series_id}
    )
    books = books_result.fetchall()
    
    return {
        "id": series.id,
        "title": series.title,
        "premise": series.premise,
        "themes": series.themes or [],
        "total_planned_books": series.total_planned_books,
        "world_rules": series.world_rules or {},
        "books": [
            {
                "id": b.id,
                "book_number": b.book_number,
                "title": b.title,
                "theme": b.theme,
                "status": b.status,
                "chapter_count": b.chapter_count,
                "target_word_count": b.target_word_count,
                "current_word_count": b.current_word_count
            }
            for b in books
        ]
    }


# ============================================================================
# BOOK ENDPOINTS
# ============================================================================

@router.post("/story/books", response_model=BookResponse)
async def create_book(
    book: BookCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new book in a series."""
    result = await db.execute(
        text("""
            INSERT INTO books (series_id, book_number, title, theme, synopsis, target_word_count)
            VALUES (:series_id, :book_number, :title, :theme, :synopsis, :target)
            RETURNING id, series_id, book_number, title, theme, status, target_word_count, current_word_count
        """),
        {
            "series_id": book.series_id,
            "book_number": book.book_number,
            "title": book.title,
            "theme": book.theme,
            "synopsis": book.synopsis,
            "target": book.target_word_count
        }
    )
    await db.commit()
    row = result.fetchone()
    
    return BookResponse(
        id=row.id,
        series_id=row.series_id,
        book_number=row.book_number,
        title=row.title,
        theme=row.theme,
        status=row.status,
        target_word_count=row.target_word_count,
        current_word_count=row.current_word_count
    )


@router.get("/story/books/{book_id}")
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    """Get a book with its chapters."""
    book_result = await db.execute(
        text("SELECT * FROM books WHERE id = :id"),
        {"id": book_id}
    )
    book = book_result.fetchone()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    chapters_result = await db.execute(
        text("""
            SELECT id, title, chapter_number, pov_character, word_count, summary
            FROM chapters
            WHERE book_id = :book_id
            ORDER BY chapter_number
        """),
        {"book_id": book_id}
    )
    chapters = chapters_result.fetchall()
    
    return {
        "id": book.id,
        "series_id": book.series_id,
        "book_number": book.book_number,
        "title": book.title,
        "theme": book.theme,
        "synopsis": book.synopsis,
        "status": book.status,
        "chapters": [
            {
                "id": c.id,
                "title": c.title,
                "chapter_number": c.chapter_number,
                "pov_character": c.pov_character,
                "word_count": c.word_count,
                "summary": c.summary
            }
            for c in chapters
        ]
    }


# ============================================================================
# FORESHADOWING ENDPOINTS
# ============================================================================

@router.post("/story/foreshadowing")
async def create_foreshadowing(
    seed: ForeshadowingCreate,
    db: AsyncSession = Depends(get_db)
):
    """Plant a new foreshadowing seed."""
    result = await db.execute(
        text("""
            INSERT INTO foreshadowing 
            (series_id, title, planted_book, planted_chapter, planted_text, 
             seed_type, subtlety, intended_payoff, status)
            VALUES (:series_id, :title, :book, :chapter, :text, 
                    :seed_type, :subtlety, :payoff, 'planted')
            RETURNING *
        """),
        {
            "series_id": seed.series_id,
            "title": seed.title,
            "book": seed.planted_book,
            "chapter": seed.planted_chapter,
            "text": seed.planted_text,
            "seed_type": seed.seed_type,
            "subtlety": seed.subtlety,
            "payoff": seed.intended_payoff
        }
    )
    await db.commit()
    row = result.fetchone()
    
    return {"message": "Foreshadowing seed planted", "id": row.id, "title": row.title}


@router.get("/story/foreshadowing/{series_id}")
async def list_foreshadowing(
    series_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List foreshadowing seeds for a series. 
    Status can be 'approved', 'pending', or seed status like 'planted', 'paid_off'.
    """
    query = """
        SELECT f.*, 
               (SELECT COUNT(*) FROM foreshadowing_reinforcements WHERE foreshadowing_id = f.id) as reinforcement_count
        FROM foreshadowing f
        WHERE f.series_id = :series_id
    """
    params = {"series_id": series_id}
    
    # Handle verification status vs foreshadowing status
    if status in ['approved', 'pending']:
        query += " AND f.verification_status = :status"
        params["status"] = status
    elif status:
        query += " AND f.status = :status"
        params["status"] = status
    
    query += " ORDER BY f.planted_book, f.planted_chapter"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    # Return as list for frontend compatibility
    return [
        {
            "id": r.id,
            "title": r.title,
            "planted_book": r.planted_book,
            "planted_chapter": r.planted_chapter,
            "planted_text": r.planted_text,
            "seed_type": r.seed_type,
            "subtlety": r.subtlety,
            "intended_payoff": r.intended_payoff,
            "payoff_book": r.payoff_book,
            "payoff_chapter": r.payoff_chapter,
            "payoff_text": getattr(r, 'payoff_text', None),
            "status": r.status,
            "verification_status": getattr(r, 'verification_status', 'approved'),
            "auto_extracted": getattr(r, 'auto_extracted', False),
            "reinforcement_count": r.reinforcement_count
        }
        for r in rows
    ]


@router.put("/story/foreshadowing/{seed_id}/payoff")
async def mark_foreshadowing_payoff(
    seed_id: int,
    update: ForeshadowingUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Mark a foreshadowing seed as paid off."""
    result = await db.execute(
        text("""
            UPDATE foreshadowing 
            SET payoff_book = :book, payoff_chapter = :chapter, 
                payoff_text = :text, status = 'paid_off',
                updated_at = NOW()
            WHERE id = :id
            RETURNING *
        """),
        {
            "id": seed_id,
            "book": update.payoff_book,
            "chapter": update.payoff_chapter,
            "text": update.payoff_text
        }
    )
    await db.commit()
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Foreshadowing seed not found")
    
    return {"message": "Foreshadowing paid off!", "seed": row.title}


# ============================================================================
# WORLD RULES ENDPOINTS
# ============================================================================

@router.post("/story/world-rules")
async def create_world_rule(
    rule: WorldRuleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new world rule."""
    result = await db.execute(
        text("""
            INSERT INTO world_rules 
            (series_id, rule_category, rule_name, rule_description, 
             exceptions, source_book, source_chapter, is_hard_rule)
            VALUES (:series_id, :category, :name, :description, 
                    :exceptions, :source_book, :source_chapter, :is_hard)
            RETURNING *
        """),
        {
            "series_id": rule.series_id,
            "category": rule.rule_category,
            "name": rule.rule_name,
            "description": rule.rule_description,
            "exceptions": rule.exceptions,
            "source_book": rule.source_book,
            "source_chapter": rule.source_chapter,
            "is_hard": rule.is_hard_rule
        }
    )
    await db.commit()
    row = result.fetchone()
    
    return {"message": "World rule created", "id": row.id}


@router.get("/story/world-rules/{series_id}")
async def list_world_rules(
    series_id: int,
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List world rules for a series. Status can be 'approved' or 'pending'."""
    query = "SELECT * FROM world_rules WHERE series_id = :series_id"
    params = {"series_id": series_id}
    
    if category:
        query += " AND rule_category = :category"
        params["category"] = category
    
    if status:
        query += " AND verification_status = :status"
        params["status"] = status
    
    query += " ORDER BY rule_category, rule_name"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    # Return as list for frontend compatibility
    return [
        {
            "id": r.id,
            "rule_category": r.rule_category,
            "rule_name": r.rule_name,
            "rule_description": r.rule_description,
            "exceptions": r.exceptions or [],
            "source_chapter": r.source_chapter,
            "is_hard_rule": r.is_hard_rule,
            "verification_status": getattr(r, 'verification_status', 'approved'),
            "auto_extracted": getattr(r, 'auto_extracted', False)
        }
        for r in rows
    ]


# ============================================================================
# CHARACTER PROFILES ENDPOINTS
# ============================================================================

@router.get("/story/characters/{series_id}")
async def list_characters(
    series_id: int,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List character profiles for a series. Status can be 'approved' or 'pending'."""
    query = "SELECT * FROM character_profiles WHERE series_id = :series_id"
    params = {"series_id": series_id}
    
    if status and status != 'all':
        query += " AND verification_status = :status"
        params["status"] = status
    
    query += " ORDER BY name"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    return [
        {
            "id": r.id,
            "name": r.name,
            "aliases": getattr(r, 'aliases', []) or [],
            "description": r.description,
            "personality": r.personality,
            "appearance": getattr(r, 'appearance', None),
            "background": getattr(r, 'background', None),
            "goals": getattr(r, 'goals', None),
            "speech_patterns": getattr(r, 'speech_patterns', None),
            "first_appearance_chapter": getattr(r, 'first_appearance_chapter', None),
            "verification_status": getattr(r, 'verification_status', 'approved'),
            "auto_extracted": getattr(r, 'auto_extracted', False),
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in rows
    ]


# ============================================================================
# STORY FACTS ENDPOINTS
# ============================================================================

@router.get("/story/facts/{series_id}")
async def list_story_facts(
    series_id: int,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List story facts for a series. Status can be 'approved' or 'pending'."""
    query = "SELECT * FROM story_facts WHERE series_id = :series_id"
    params = {"series_id": series_id}
    
    if status and status != 'all':
        query += " AND verification_status = :status"
        params["status"] = status
    
    if category:
        query += " AND fact_category = :category"
        params["category"] = category
    
    query += " ORDER BY established_in_chapter DESC, created_at DESC"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    return [
        {
            "id": r.id,
            "fact_description": r.fact_description,
            "fact_category": r.fact_category,
            "established_in_chapter": r.established_in_chapter,
            "is_secret": getattr(r, 'is_secret', False),
            "importance": getattr(r, 'importance', 'normal'),
            "verification_status": getattr(r, 'verification_status', 'approved'),
            "auto_extracted": getattr(r, 'auto_extracted', False),
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in rows
    ]


# ============================================================================
# CHARACTER KNOWLEDGE ENDPOINTS
# ============================================================================

@router.post("/story/character-knowledge")
async def add_character_knowledge(
    data: CharacterKnowledgeAdd,
    db: AsyncSession = Depends(get_db)
):
    """Add a fact that a character knows."""
    # Get or create character
    char_result = await db.execute(
        text("""
            SELECT id FROM character_profiles 
            WHERE series_id = :series_id AND name ILIKE :name
        """),
        {"series_id": data.series_id, "name": f"%{data.character_name}%"}
    )
    char = char_result.fetchone()
    
    if not char:
        raise HTTPException(status_code=404, detail=f"Character '{data.character_name}' not found")
    
    # Create the fact
    fact_result = await db.execute(
        text("""
            INSERT INTO story_facts 
            (series_id, fact_description, fact_category, established_in_chapter, is_secret)
            VALUES (:series_id, :description, :category, :chapter, :is_secret)
            RETURNING id
        """),
        {
            "series_id": data.series_id,
            "description": data.fact_description,
            "category": data.fact_category,
            "chapter": data.learned_in_chapter,
            "is_secret": data.is_secret
        }
    )
    fact = fact_result.fetchone()
    
    # Link to character
    await db.execute(
        text("""
            INSERT INTO character_knowledge 
            (character_id, fact_id, learned_in_chapter, learned_how, certainty)
            VALUES (:char_id, :fact_id, :chapter, :how, :certainty)
            ON CONFLICT (character_id, fact_id) DO UPDATE
            SET learned_in_chapter = :chapter, learned_how = :how, certainty = :certainty
        """),
        {
            "char_id": char.id,
            "fact_id": fact.id,
            "chapter": data.learned_in_chapter,
            "how": data.learned_how,
            "certainty": data.certainty
        }
    )
    await db.commit()
    
    return {"message": f"Knowledge added for {data.character_name}", "fact_id": fact.id}


@router.get("/story/character-knowledge/{series_id}/{character_name}")
async def get_character_knowledge(
    series_id: int,
    character_name: str,
    as_of_chapter: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get what a character knows."""
    char_result = await db.execute(
        text("""
            SELECT id, name FROM character_profiles 
            WHERE series_id = :series_id AND name ILIKE :name
        """),
        {"series_id": series_id, "name": f"%{character_name}%"}
    )
    char = char_result.fetchone()
    
    if not char:
        raise HTTPException(status_code=404, detail=f"Character '{character_name}' not found")
    
    query = """
        SELECT sf.fact_description, sf.fact_category, sf.is_secret,
               ck.learned_in_chapter, ck.learned_how, ck.certainty
        FROM character_knowledge ck
        JOIN story_facts sf ON ck.fact_id = sf.id
        WHERE ck.character_id = :char_id
    """
    params = {"char_id": char.id}
    
    if as_of_chapter:
        query += " AND ck.learned_in_chapter <= :chapter"
        params["chapter"] = as_of_chapter
    
    query += " ORDER BY ck.learned_in_chapter"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    return {
        "character": char.name,
        "as_of_chapter": as_of_chapter,
        "knowledge": [
            {
                "fact": r.fact_description,
                "category": r.fact_category,
                "is_secret": r.is_secret,
                "learned_in_chapter": r.learned_in_chapter,
                "learned_how": r.learned_how,
                "certainty": r.certainty
            }
            for r in rows
        ]
    }


# ============================================================================
# LLM ANALYSIS ENDPOINTS
# ============================================================================

@router.post("/story/analyze/knowledge-check")
async def analyze_knowledge_check(request: KnowledgeCheckRequest):
    """Use LLM to check if character action is consistent with their knowledge."""
    service = get_story_analysis_service()
    result = await service.check_character_knowledge(
        character_name=request.character_name,
        proposed_action=request.proposed_action,
        current_chapter=request.current_chapter,
        series_id=request.series_id
    )
    return result


@router.post("/story/analyze/knowledge-query")
async def analyze_knowledge_query(request: KnowledgeQueryRequest):
    """Ask LLM what a character knows about something."""
    service = get_story_analysis_service()
    result = await service.query_character_knowledge(
        character_name=request.character_name,
        question=request.question,
        as_of_chapter=request.as_of_chapter,
        series_id=request.series_id
    )
    return result


@router.post("/story/analyze/consistency")
async def analyze_consistency(request: ConsistencyCheckRequest):
    """Use LLM to check content for consistency issues."""
    service = get_story_analysis_service()
    result = await service.check_consistency(
        content=request.content,
        series_id=request.series_id,
        check_types=request.check_types
    )
    return result


@router.post("/story/analyze/foreshadowing")
async def analyze_foreshadowing(request: ForeshadowingAnalysisRequest):
    """Use LLM to analyze foreshadowing opportunities."""
    service = get_story_analysis_service()
    result = await service.analyze_foreshadowing_opportunities(
        chapter_content=request.chapter_content,
        series_id=request.series_id,
        current_book=request.current_book,
        current_chapter=request.current_chapter
    )
    return result


@router.get("/story/analyze/position/{series_id}/{book_id}/{chapter_number}")
async def get_story_position(
    series_id: int,
    book_id: int,
    chapter_number: int
):
    """Get chapter position context for AI-enhanced writing."""
    service = get_story_analysis_service()
    result = await service.get_chapter_position_context(
        series_id=series_id,
        book_id=book_id,
        chapter_number=chapter_number
    )
    return result

