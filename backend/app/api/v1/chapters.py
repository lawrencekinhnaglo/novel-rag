"""Chapters API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
import json
import asyncio

from app.database.postgres import get_db
from app.database.qdrant_client import get_vector_manager
from app.services.embeddings import generate_embedding
from app.services.auto_analysis import trigger_chapter_analysis
from app.api.v1.models import ChapterCreate, ChapterUpdate, ChapterResponse, IdeaCreate, IdeaResponse

router = APIRouter()


@router.post("/chapters", response_model=ChapterResponse)
async def create_chapter(
    chapter: ChapterCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chapter with optional automatic analysis."""
    # Calculate word count
    word_count = len(chapter.content.split())
    
    # Generate embedding
    embedding = generate_embedding(chapter.content)
    
    # Save to PostgreSQL (with new fields)
    result = await db.execute(
        text("""
            INSERT INTO chapters (title, content, chapter_number, book_id, pov_character, 
                                  word_count, embedding, language, metadata)
            VALUES (:title, :content, :chapter_number, :book_id, :pov_character,
                    :word_count, :embedding, :language, :metadata)
            RETURNING id, title, content, chapter_number, word_count, created_at, updated_at
        """),
        {
            "title": chapter.title,
            "content": chapter.content,
            "chapter_number": chapter.chapter_number,
            "book_id": chapter.book_id,
            "pov_character": chapter.pov_character,
            "word_count": word_count,
            "embedding": str(embedding),
            "language": chapter.language,
            "metadata": json.dumps(chapter.metadata)
        }
    )
    await db.commit()
    row = result.fetchone()
    
    # Save to Qdrant
    vector_manager = get_vector_manager()
    vector_manager.upsert_vectors(
        collection="chapters",
        points=[{
            "id": row.id,
            "vector": embedding,
            "payload": {
                "id": row.id,
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "content": chapter.content[:1000],  # Store first 1000 chars
                "word_count": word_count
            }
        }]
    )
    
    # 🤖 Trigger automatic LLM analysis in background
    if chapter.auto_analyze and chapter.series_id and chapter.book_id:
        background_tasks.add_task(
            run_chapter_analysis,
            chapter_id=row.id,
            chapter_content=chapter.content,
            book_id=chapter.book_id,
            series_id=chapter.series_id,
            chapter_number=chapter.chapter_number or 1
        )
    
    return ChapterResponse(
        id=row.id,
        title=row.title,
        content=row.content,
        chapter_number=row.chapter_number,
        word_count=row.word_count,
        created_at=row.created_at,
        updated_at=row.updated_at
    )


async def run_chapter_analysis(
    chapter_id: int,
    chapter_content: str,
    book_id: int,
    series_id: int,
    chapter_number: int
):
    """Run analysis in background and store results."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        results = await trigger_chapter_analysis(
            chapter_id=chapter_id,
            chapter_content=chapter_content,
            book_id=book_id,
            series_id=series_id,
            chapter_number=chapter_number
        )
        logger.info(f"Chapter {chapter_id} auto-analysis complete: {list(results.keys())}")
    except Exception as e:
        logger.error(f"Chapter {chapter_id} auto-analysis failed: {e}")


@router.get("/chapters", response_model=List[ChapterResponse])
async def list_chapters(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List all chapters."""
    result = await db.execute(
        text("""
            SELECT id, title, content, chapter_number, word_count, created_at, updated_at
            FROM chapters
            ORDER BY chapter_number ASC NULLS LAST, created_at ASC
            LIMIT :limit OFFSET :skip
        """),
        {"limit": limit, "skip": skip}
    )
    rows = result.fetchall()
    
    return [
        ChapterResponse(
            id=row.id,
            title=row.title,
            content=row.content,
            chapter_number=row.chapter_number,
            word_count=row.word_count,
            created_at=row.created_at,
            updated_at=row.updated_at
        )
        for row in rows
    ]


@router.get("/chapters/{chapter_id}", response_model=ChapterResponse)
async def get_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific chapter."""
    result = await db.execute(
        text("""
            SELECT id, title, content, chapter_number, word_count, created_at, updated_at
            FROM chapters
            WHERE id = :chapter_id
        """),
        {"chapter_id": chapter_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return ChapterResponse(
        id=row.id,
        title=row.title,
        content=row.content,
        chapter_number=row.chapter_number,
        word_count=row.word_count,
        created_at=row.created_at,
        updated_at=row.updated_at
    )


@router.put("/chapters/{chapter_id}", response_model=ChapterResponse)
async def update_chapter(
    chapter_id: int,
    chapter: ChapterUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a chapter."""
    # Build update query dynamically
    updates = []
    params = {"chapter_id": chapter_id}
    
    if chapter.title is not None:
        updates.append("title = :title")
        params["title"] = chapter.title
    
    if chapter.content is not None:
        updates.append("content = :content")
        params["content"] = chapter.content
        params["word_count"] = len(chapter.content.split())
        updates.append("word_count = :word_count")
        
        # Update embedding
        embedding = generate_embedding(chapter.content)
        params["embedding"] = str(embedding)
        updates.append("embedding = :embedding")
    
    if chapter.chapter_number is not None:
        updates.append("chapter_number = :chapter_number")
        params["chapter_number"] = chapter.chapter_number
    
    if chapter.metadata is not None:
        updates.append("metadata = :metadata")
        params["metadata"] = json.dumps(chapter.metadata)
    
    if not updates:
        return await get_chapter(chapter_id, db)
    
    updates.append("updated_at = NOW()")
    
    query = f"""
        UPDATE chapters 
        SET {', '.join(updates)}
        WHERE id = :chapter_id
        RETURNING id, title, content, chapter_number, word_count, created_at, updated_at
    """
    
    result = await db.execute(text(query), params)
    await db.commit()
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Update Qdrant if content changed
    if chapter.content is not None:
        vector_manager = get_vector_manager()
        vector_manager.upsert_vectors(
            collection="chapters",
            points=[{
                "id": row.id,
                "vector": embedding,
                "payload": {
                    "id": row.id,
                    "title": row.title,
                    "chapter_number": row.chapter_number,
                    "content": row.content[:1000],
                    "word_count": row.word_count
                }
            }]
        )
    
    return ChapterResponse(
        id=row.id,
        title=row.title,
        content=row.content,
        chapter_number=row.chapter_number,
        word_count=row.word_count,
        created_at=row.created_at,
        updated_at=row.updated_at
    )


@router.delete("/chapters/{chapter_id}")
async def delete_chapter(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a chapter."""
    result = await db.execute(
        text("DELETE FROM chapters WHERE id = :chapter_id RETURNING id"),
        {"chapter_id": chapter_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Delete from Qdrant
    vector_manager = get_vector_manager()
    vector_manager.delete_vectors("chapters", [str(chapter_id)])
    
    return {"message": "Chapter deleted successfully"}


# Ideas endpoints
@router.post("/ideas", response_model=IdeaResponse)
async def create_idea(
    idea: IdeaCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new idea/note."""
    embedding = generate_embedding(idea.content)
    
    result = await db.execute(
        text("""
            INSERT INTO ideas (title, content, category, embedding, tags, related_chapters)
            VALUES (:title, :content, :category, :embedding, :tags, :related_chapters)
            RETURNING id, title, content, category, tags, related_chapters, created_at
        """),
        {
            "title": idea.title,
            "content": idea.content,
            "category": idea.category,
            "embedding": str(embedding),
            "tags": idea.tags,
            "related_chapters": idea.related_chapters
        }
    )
    await db.commit()
    row = result.fetchone()
    
    # Save to Qdrant
    vector_manager = get_vector_manager()
    vector_manager.upsert_vectors(
        collection="ideas",
        points=[{
            "id": row.id,
            "vector": embedding,
            "payload": {
                "id": row.id,
                "title": idea.title,
                "content": idea.content[:500],
                "category": idea.category,
                "tags": idea.tags
            }
        }]
    )
    
    return IdeaResponse(
        id=row.id,
        title=row.title,
        content=row.content,
        category=row.category,
        tags=row.tags or [],
        related_chapters=row.related_chapters or [],
        created_at=row.created_at
    )


@router.get("/ideas", response_model=List[IdeaResponse])
async def list_ideas(
    category: str = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List all ideas."""
    if category:
        result = await db.execute(
            text("""
                SELECT id, title, content, category, tags, related_chapters, created_at
                FROM ideas
                WHERE category = :category
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :skip
            """),
            {"category": category, "limit": limit, "skip": skip}
        )
    else:
        result = await db.execute(
            text("""
                SELECT id, title, content, category, tags, related_chapters, created_at
                FROM ideas
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :skip
            """),
            {"limit": limit, "skip": skip}
        )
    
    rows = result.fetchall()
    return [
        IdeaResponse(
            id=row.id,
            title=row.title,
            content=row.content,
            category=row.category,
            tags=row.tags or [],
            related_chapters=row.related_chapters or [],
            created_at=row.created_at
        )
        for row in rows
    ]


@router.delete("/ideas/{idea_id}")
async def delete_idea(
    idea_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete an idea."""
    result = await db.execute(
        text("DELETE FROM ideas WHERE id = :idea_id RETURNING id"),
        {"idea_id": idea_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Idea not found")
    
    vector_manager = get_vector_manager()
    vector_manager.delete_vectors("ideas", [str(idea_id)])
    
    return {"message": "Idea deleted successfully"}

