"""Story Branches API endpoints - Alternative storylines exploration."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel

from app.database.postgres import get_db
from app.services.embeddings import generate_embedding

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class BranchCreate(BaseModel):
    series_id: int
    branch_name: str
    branch_description: Optional[str]
    branch_point_chapter_id: Optional[int]
    divergence_description: Optional[str]

class BranchUpdate(BaseModel):
    branch_name: Optional[str]
    branch_description: Optional[str]
    divergence_description: Optional[str]
    is_active: Optional[bool]

class BranchChapterCreate(BaseModel):
    branch_id: int
    title: str
    content: str
    chapter_number: Optional[int]
    notes: Optional[str]

class BranchChapterUpdate(BaseModel):
    title: Optional[str]
    content: Optional[str]
    chapter_number: Optional[int]
    notes: Optional[str]


# ============================================================================
# STORY BRANCHES
# ============================================================================

@router.get("/branches/{series_id}")
async def get_branches(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get all story branches for a series."""
    result = await db.execute(
        text("""
            SELECT sb.*, c.title as branch_point_chapter_title,
                   (SELECT COUNT(*) FROM branch_chapters WHERE branch_id = sb.id) as chapter_count
            FROM story_branches sb
            LEFT JOIN chapters c ON sb.branch_point_chapter_id = c.id
            WHERE sb.series_id = :series_id
            ORDER BY sb.created_at DESC
        """),
        {"series_id": series_id}
    )
    branches = result.fetchall()
    return [
        {
            "id": b.id,
            "series_id": b.series_id,
            "branch_name": b.branch_name,
            "branch_description": b.branch_description,
            "branch_point_chapter_id": b.branch_point_chapter_id,
            "branch_point_chapter_title": b.branch_point_chapter_title,
            "divergence_description": b.divergence_description,
            "is_active": b.is_active,
            "is_merged": b.is_merged,
            "chapter_count": b.chapter_count,
            "created_at": b.created_at.isoformat() if b.created_at else None
        }
        for b in branches
    ]


@router.post("/branches")
async def create_branch(
    branch: BranchCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new story branch."""
    result = await db.execute(
        text("""
            INSERT INTO story_branches (series_id, branch_name, branch_description,
                                        branch_point_chapter_id, divergence_description)
            VALUES (:series_id, :branch_name, :branch_description,
                    :branch_point_chapter_id, :divergence_description)
            RETURNING *
        """),
        {
            "series_id": branch.series_id,
            "branch_name": branch.branch_name,
            "branch_description": branch.branch_description,
            "branch_point_chapter_id": branch.branch_point_chapter_id,
            "divergence_description": branch.divergence_description
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Branch created successfully"}


@router.put("/branches/{branch_id}")
async def update_branch(
    branch_id: int,
    branch: BranchUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a story branch."""
    updates = []
    params = {"branch_id": branch_id}
    
    for field in ["branch_name", "branch_description", "divergence_description", "is_active"]:
        value = getattr(branch, field)
        if value is not None:
            updates.append(f"{field} = :{field}")
            params[field] = value
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    updates.append("updated_at = NOW()")
    
    result = await db.execute(
        text(f"UPDATE story_branches SET {', '.join(updates)} WHERE id = :branch_id RETURNING *"),
        params
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Branch not found")
    
    return {"message": "Branch updated successfully"}


@router.delete("/branches/{branch_id}")
async def delete_branch(branch_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a story branch and all its chapters."""
    result = await db.execute(
        text("DELETE FROM story_branches WHERE id = :id RETURNING id"),
        {"id": branch_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Branch not found")
    
    return {"message": "Branch deleted successfully"}


# ============================================================================
# BRANCH CHAPTERS
# ============================================================================

@router.get("/branches/{branch_id}/chapters")
async def get_branch_chapters(branch_id: int, db: AsyncSession = Depends(get_db)):
    """Get all chapters in a branch."""
    result = await db.execute(
        text("""
            SELECT * FROM branch_chapters
            WHERE branch_id = :branch_id
            ORDER BY chapter_number NULLS LAST, created_at
        """),
        {"branch_id": branch_id}
    )
    chapters = result.fetchall()
    return [
        {
            "id": c.id,
            "branch_id": c.branch_id,
            "title": c.title,
            "content": c.content[:500] + "..." if len(c.content) > 500 else c.content,
            "chapter_number": c.chapter_number,
            "word_count": c.word_count,
            "notes": c.notes,
            "created_at": c.created_at.isoformat() if c.created_at else None
        }
        for c in chapters
    ]


@router.get("/branches/chapters/{chapter_id}")
async def get_branch_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific branch chapter with full content."""
    result = await db.execute(
        text("SELECT * FROM branch_chapters WHERE id = :id"),
        {"id": chapter_id}
    )
    chapter = result.fetchone()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return {
        "id": chapter.id,
        "branch_id": chapter.branch_id,
        "title": chapter.title,
        "content": chapter.content,
        "chapter_number": chapter.chapter_number,
        "word_count": chapter.word_count,
        "notes": chapter.notes,
        "created_at": chapter.created_at.isoformat() if chapter.created_at else None
    }


@router.post("/branches/chapters")
async def create_branch_chapter(
    chapter: BranchChapterCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new chapter in a branch."""
    word_count = len(chapter.content.split())
    embedding = generate_embedding(chapter.content)
    
    result = await db.execute(
        text("""
            INSERT INTO branch_chapters (branch_id, title, content, chapter_number,
                                         word_count, embedding, notes)
            VALUES (:branch_id, :title, :content, :chapter_number,
                    :word_count, :embedding, :notes)
            RETURNING *
        """),
        {
            "branch_id": chapter.branch_id,
            "title": chapter.title,
            "content": chapter.content,
            "chapter_number": chapter.chapter_number,
            "word_count": word_count,
            "embedding": str(embedding),
            "notes": chapter.notes
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "word_count": word_count, "message": "Branch chapter created successfully"}


@router.put("/branches/chapters/{chapter_id}")
async def update_branch_chapter(
    chapter_id: int,
    chapter: BranchChapterUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a branch chapter."""
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
        embedding = generate_embedding(chapter.content)
        params["embedding"] = str(embedding)
        updates.append("embedding = :embedding")
    if chapter.chapter_number is not None:
        updates.append("chapter_number = :chapter_number")
        params["chapter_number"] = chapter.chapter_number
    if chapter.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = chapter.notes
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    updates.append("updated_at = NOW()")
    
    result = await db.execute(
        text(f"UPDATE branch_chapters SET {', '.join(updates)} WHERE id = :chapter_id RETURNING *"),
        params
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return {"message": "Branch chapter updated successfully"}


@router.delete("/branches/chapters/{chapter_id}")
async def delete_branch_chapter(chapter_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a branch chapter."""
    result = await db.execute(
        text("DELETE FROM branch_chapters WHERE id = :id RETURNING id"),
        {"id": chapter_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return {"message": "Branch chapter deleted successfully"}


# ============================================================================
# BRANCH COMPARISON
# ============================================================================

@router.get("/branches/compare/{branch_id}")
async def compare_branch_to_main(branch_id: int, db: AsyncSession = Depends(get_db)):
    """Compare a branch to the main storyline."""
    # Get branch info
    branch_result = await db.execute(
        text("""
            SELECT sb.*, s.title as series_title
            FROM story_branches sb
            JOIN series s ON sb.series_id = s.id
            WHERE sb.id = :branch_id
        """),
        {"branch_id": branch_id}
    )
    branch = branch_result.fetchone()
    
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    # Get branch chapters
    branch_chapters_result = await db.execute(
        text("SELECT id, title, word_count FROM branch_chapters WHERE branch_id = :id ORDER BY chapter_number"),
        {"id": branch_id}
    )
    branch_chapters = branch_chapters_result.fetchall()
    
    # Get main chapters after branch point
    main_chapters_result = await db.execute(
        text("""
            SELECT c.id, c.title, c.word_count, c.chapter_number
            FROM chapters c
            JOIN books b ON c.book_id = b.id
            WHERE b.series_id = :series_id
            AND c.chapter_number >= COALESCE(
                (SELECT chapter_number FROM chapters WHERE id = :branch_point_id),
                1
            )
            ORDER BY c.chapter_number
        """),
        {
            "series_id": branch.series_id,
            "branch_point_id": branch.branch_point_chapter_id
        }
    )
    main_chapters = main_chapters_result.fetchall()
    
    return {
        "branch": {
            "id": branch.id,
            "name": branch.branch_name,
            "divergence": branch.divergence_description,
            "chapters": [{"id": c.id, "title": c.title, "word_count": c.word_count} for c in branch_chapters],
            "total_words": sum(c.word_count or 0 for c in branch_chapters)
        },
        "main": {
            "series": branch.series_title,
            "chapters_after_branch": [
                {"id": c.id, "title": c.title, "word_count": c.word_count, "chapter_number": c.chapter_number}
                for c in main_chapters
            ],
            "total_words": sum(c.word_count or 0 for c in main_chapters)
        }
    }


