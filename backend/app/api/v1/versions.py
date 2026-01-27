"""Version control API for chapter revisions."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
from app.database.postgres import get_db
from datetime import datetime
import logging
import json
import difflib

logger = logging.getLogger(__name__)

router = APIRouter()


class VersionCreate(BaseModel):
    """Create a new version."""
    chapter_id: int
    content: str
    title: Optional[str] = None
    change_summary: Optional[str] = None


class VersionResponse(BaseModel):
    """Version response."""
    id: int
    chapter_id: int
    version_number: int
    title: Optional[str]
    content: str
    word_count: int
    change_summary: Optional[str]
    created_at: datetime


class DiffResponse(BaseModel):
    """Diff response between two versions."""
    version_a: int
    version_b: int
    unified_diff: str
    additions: int
    deletions: int
    changes: List[dict]


@router.post("/chapters/{chapter_id}/versions", response_model=VersionResponse)
async def create_version(
    chapter_id: int,
    version: VersionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new version of a chapter (snapshot)."""
    
    # Check chapter exists
    chapter_result = await db.execute(
        text("SELECT id, title FROM chapters WHERE id = :id"),
        {"id": chapter_id}
    )
    chapter = chapter_result.fetchone()
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    
    # Get next version number
    version_result = await db.execute(
        text("""
            SELECT COALESCE(MAX(version_number), 0) + 1 as next_version
            FROM chapter_versions
            WHERE chapter_id = :chapter_id
        """),
        {"chapter_id": chapter_id}
    )
    next_version = version_result.scalar()
    
    # Calculate word count
    word_count = len(version.content.split()) if version.content else 0
    
    # Insert version
    insert_result = await db.execute(
        text("""
            INSERT INTO chapter_versions 
            (chapter_id, version_number, title, content, word_count, change_summary)
            VALUES (:chapter_id, :version_number, :title, :content, :word_count, :change_summary)
            RETURNING id, chapter_id, version_number, title, content, word_count, change_summary, created_at
        """),
        {
            "chapter_id": chapter_id,
            "version_number": next_version,
            "title": version.title or chapter.title,
            "content": version.content,
            "word_count": word_count,
            "change_summary": version.change_summary
        }
    )
    row = insert_result.fetchone()
    await db.commit()
    
    return VersionResponse(
        id=row.id,
        chapter_id=row.chapter_id,
        version_number=row.version_number,
        title=row.title,
        content=row.content,
        word_count=row.word_count,
        change_summary=row.change_summary,
        created_at=row.created_at
    )


@router.get("/chapters/{chapter_id}/versions", response_model=List[VersionResponse])
async def list_versions(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """List all versions of a chapter."""
    
    result = await db.execute(
        text("""
            SELECT id, chapter_id, version_number, title, content, word_count, change_summary, created_at
            FROM chapter_versions
            WHERE chapter_id = :chapter_id
            ORDER BY version_number DESC
        """),
        {"chapter_id": chapter_id}
    )
    
    return [
        VersionResponse(
            id=row.id,
            chapter_id=row.chapter_id,
            version_number=row.version_number,
            title=row.title,
            content=row.content,
            word_count=row.word_count,
            change_summary=row.change_summary,
            created_at=row.created_at
        )
        for row in result.fetchall()
    ]


@router.get("/chapters/{chapter_id}/versions/{version_number}", response_model=VersionResponse)
async def get_version(
    chapter_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific version of a chapter."""
    
    result = await db.execute(
        text("""
            SELECT id, chapter_id, version_number, title, content, word_count, change_summary, created_at
            FROM chapter_versions
            WHERE chapter_id = :chapter_id AND version_number = :version_number
        """),
        {"chapter_id": chapter_id, "version_number": version_number}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(404, "Version not found")
    
    return VersionResponse(
        id=row.id,
        chapter_id=row.chapter_id,
        version_number=row.version_number,
        title=row.title,
        content=row.content,
        word_count=row.word_count,
        change_summary=row.change_summary,
        created_at=row.created_at
    )


@router.get("/chapters/{chapter_id}/versions/diff/{version_a}/{version_b}", response_model=DiffResponse)
async def diff_versions(
    chapter_id: int,
    version_a: int,
    version_b: int,
    db: AsyncSession = Depends(get_db)
):
    """Get diff between two versions."""
    
    # Get both versions
    result = await db.execute(
        text("""
            SELECT version_number, content
            FROM chapter_versions
            WHERE chapter_id = :chapter_id AND version_number IN (:va, :vb)
            ORDER BY version_number
        """),
        {"chapter_id": chapter_id, "va": version_a, "vb": version_b}
    )
    rows = result.fetchall()
    
    if len(rows) != 2:
        raise HTTPException(404, "One or both versions not found")
    
    content_a = rows[0].content if rows[0].version_number == version_a else rows[1].content
    content_b = rows[1].content if rows[1].version_number == version_b else rows[0].content
    
    # Generate unified diff
    lines_a = content_a.split('\n')
    lines_b = content_b.split('\n')
    
    diff = list(difflib.unified_diff(
        lines_a, lines_b,
        fromfile=f"Version {version_a}",
        tofile=f"Version {version_b}",
        lineterm=''
    ))
    
    # Count additions and deletions
    additions = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
    deletions = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    
    # Generate change summary
    changes = []
    for i, line in enumerate(diff):
        if line.startswith('+') and not line.startswith('+++'):
            changes.append({"type": "addition", "line": i, "content": line[1:]})
        elif line.startswith('-') and not line.startswith('---'):
            changes.append({"type": "deletion", "line": i, "content": line[1:]})
    
    return DiffResponse(
        version_a=version_a,
        version_b=version_b,
        unified_diff='\n'.join(diff),
        additions=additions,
        deletions=deletions,
        changes=changes[:50]  # Limit for UI
    )


@router.post("/chapters/{chapter_id}/versions/{version_number}/restore")
async def restore_version(
    chapter_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db)
):
    """Restore a chapter to a specific version."""
    
    # Get the version
    version_result = await db.execute(
        text("""
            SELECT content, title
            FROM chapter_versions
            WHERE chapter_id = :chapter_id AND version_number = :version_number
        """),
        {"chapter_id": chapter_id, "version_number": version_number}
    )
    version = version_result.fetchone()
    
    if not version:
        raise HTTPException(404, "Version not found")
    
    # First, create a backup version of current state
    current_result = await db.execute(
        text("SELECT content, title FROM chapters WHERE id = :id"),
        {"id": chapter_id}
    )
    current = current_result.fetchone()
    
    if current:
        # Get next version number for backup
        next_version_result = await db.execute(
            text("""
                SELECT COALESCE(MAX(version_number), 0) + 1 as next_version
                FROM chapter_versions
                WHERE chapter_id = :chapter_id
            """),
            {"chapter_id": chapter_id}
        )
        next_version = next_version_result.scalar()
        
        # Create backup version
        await db.execute(
            text("""
                INSERT INTO chapter_versions 
                (chapter_id, version_number, title, content, word_count, change_summary)
                VALUES (:chapter_id, :version_number, :title, :content, :word_count, :change_summary)
            """),
            {
                "chapter_id": chapter_id,
                "version_number": next_version,
                "title": current.title,
                "content": current.content,
                "word_count": len(current.content.split()) if current.content else 0,
                "change_summary": f"Auto-backup before restoring to version {version_number}"
            }
        )
    
    # Update chapter with restored content
    word_count = len(version.content.split()) if version.content else 0
    await db.execute(
        text("""
            UPDATE chapters 
            SET content = :content, title = :title, word_count = :word_count, updated_at = NOW()
            WHERE id = :id
        """),
        {
            "id": chapter_id,
            "content": version.content,
            "title": version.title,
            "word_count": word_count
        }
    )
    
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Restored chapter to version {version_number}",
        "backup_created": True
    }


@router.delete("/chapters/{chapter_id}/versions/{version_number}")
async def delete_version(
    chapter_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific version (cannot delete the latest)."""
    
    # Check if this is the latest version
    latest_result = await db.execute(
        text("""
            SELECT MAX(version_number) as latest
            FROM chapter_versions
            WHERE chapter_id = :chapter_id
        """),
        {"chapter_id": chapter_id}
    )
    latest = latest_result.scalar()
    
    if version_number == latest:
        raise HTTPException(400, "Cannot delete the latest version")
    
    # Delete the version
    await db.execute(
        text("""
            DELETE FROM chapter_versions
            WHERE chapter_id = :chapter_id AND version_number = :version_number
        """),
        {"chapter_id": chapter_id, "version_number": version_number}
    )
    await db.commit()
    
    return {"status": "success", "message": f"Deleted version {version_number}"}


@router.post("/chapters/{chapter_id}/auto-save")
async def auto_save_version(
    chapter_id: int,
    content: str,
    db: AsyncSession = Depends(get_db)
):
    """Auto-save current chapter state as a new version if significantly changed."""
    
    # Get latest version
    latest_result = await db.execute(
        text("""
            SELECT content, version_number
            FROM chapter_versions
            WHERE chapter_id = :chapter_id
            ORDER BY version_number DESC
            LIMIT 1
        """),
        {"chapter_id": chapter_id}
    )
    latest = latest_result.fetchone()
    
    # Check if content has changed significantly (more than 50 characters)
    if latest:
        diff_length = abs(len(content) - len(latest.content))
        if diff_length < 50:
            return {"status": "skipped", "message": "Not enough changes to save"}
    
    # Create new version
    version = VersionCreate(
        chapter_id=chapter_id,
        content=content,
        change_summary="Auto-save"
    )
    
    return await create_version(chapter_id, version, db)
