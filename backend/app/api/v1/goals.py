"""Writing Goals API endpoints - Progress tracking and goal management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime, timedelta

from app.database.postgres import get_db

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class WritingGoalCreate(BaseModel):
    series_id: int
    goal_type: str  # daily, weekly, monthly, total, deadline
    target_words: Optional[int]
    target_chapters: Optional[int]
    deadline: Optional[date]

class WritingGoalUpdate(BaseModel):
    target_words: Optional[int]
    target_chapters: Optional[int]
    deadline: Optional[date]
    is_active: Optional[bool]

class WritingSessionCreate(BaseModel):
    series_id: int
    chapter_id: Optional[int]
    words_written: int
    duration_minutes: Optional[int]
    notes: Optional[str]

class DailyWordCountUpdate(BaseModel):
    series_id: int
    words_added: int = 0
    words_deleted: int = 0
    chapter_id: Optional[int]


# ============================================================================
# WRITING GOALS
# ============================================================================

@router.get("/goals/{series_id}")
async def get_goals(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get all writing goals for a series."""
    result = await db.execute(
        text("""
            SELECT * FROM writing_goals
            WHERE series_id = :series_id
            ORDER BY is_active DESC, created_at DESC
        """),
        {"series_id": series_id}
    )
    goals = result.fetchall()
    return [
        {
            "id": g.id,
            "series_id": g.series_id,
            "goal_type": g.goal_type,
            "target_words": g.target_words,
            "target_chapters": g.target_chapters,
            "deadline": g.deadline.isoformat() if g.deadline else None,
            "is_active": g.is_active,
            "created_at": g.created_at.isoformat() if g.created_at else None
        }
        for g in goals
    ]


@router.post("/goals")
async def create_goal(
    goal: WritingGoalCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new writing goal."""
    result = await db.execute(
        text("""
            INSERT INTO writing_goals (series_id, goal_type, target_words,
                                       target_chapters, deadline)
            VALUES (:series_id, :goal_type, :target_words,
                    :target_chapters, :deadline)
            RETURNING *
        """),
        {
            "series_id": goal.series_id,
            "goal_type": goal.goal_type,
            "target_words": goal.target_words,
            "target_chapters": goal.target_chapters,
            "deadline": goal.deadline
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Writing goal created successfully"}


@router.put("/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    goal: WritingGoalUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a writing goal."""
    updates = []
    params = {"goal_id": goal_id}
    
    for field in ["target_words", "target_chapters", "deadline", "is_active"]:
        value = getattr(goal, field)
        if value is not None:
            updates.append(f"{field} = :{field}")
            params[field] = value
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    result = await db.execute(
        text(f"UPDATE writing_goals SET {', '.join(updates)} WHERE id = :goal_id RETURNING *"),
        params
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return {"message": "Writing goal updated successfully"}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a writing goal."""
    result = await db.execute(
        text("DELETE FROM writing_goals WHERE id = :id RETURNING id"),
        {"id": goal_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Goal not found")
    
    return {"message": "Writing goal deleted successfully"}


# ============================================================================
# WRITING SESSIONS
# ============================================================================

@router.get("/goals/sessions/{series_id}")
async def get_writing_sessions(
    series_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get writing sessions for a series within the specified number of days."""
    result = await db.execute(
        text("""
            SELECT ws.*, c.title as chapter_title
            FROM writing_sessions ws
            LEFT JOIN chapters c ON ws.chapter_id = c.id
            WHERE ws.series_id = :series_id
            AND ws.session_date >= CURRENT_DATE - :days
            ORDER BY ws.session_date DESC, ws.created_at DESC
        """),
        {"series_id": series_id, "days": days}
    )
    sessions = result.fetchall()
    return [
        {
            "id": s.id,
            "series_id": s.series_id,
            "chapter_id": s.chapter_id,
            "chapter_title": s.chapter_title,
            "session_date": s.session_date.isoformat() if s.session_date else None,
            "words_written": s.words_written,
            "duration_minutes": s.duration_minutes,
            "notes": s.notes
        }
        for s in sessions
    ]


@router.post("/goals/sessions")
async def create_writing_session(
    session: WritingSessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Log a writing session."""
    result = await db.execute(
        text("""
            INSERT INTO writing_sessions (series_id, chapter_id, words_written,
                                          duration_minutes, notes)
            VALUES (:series_id, :chapter_id, :words_written,
                    :duration_minutes, :notes)
            RETURNING *
        """),
        {
            "series_id": session.series_id,
            "chapter_id": session.chapter_id,
            "words_written": session.words_written,
            "duration_minutes": session.duration_minutes,
            "notes": session.notes
        }
    )
    await db.commit()
    row = result.fetchone()
    
    # Also update daily word count
    await db.execute(
        text("""
            INSERT INTO daily_word_counts (series_id, count_date, words_added, net_words, chapters_worked_on)
            VALUES (:series_id, CURRENT_DATE, :words, :words, 
                    CASE WHEN :chapter_id IS NOT NULL THEN ARRAY[:chapter_id] ELSE ARRAY[]::INTEGER[] END)
            ON CONFLICT (series_id, count_date) DO UPDATE
            SET words_added = daily_word_counts.words_added + :words,
                net_words = daily_word_counts.net_words + :words,
                chapters_worked_on = (
                    SELECT array_agg(DISTINCT elem)
                    FROM unnest(daily_word_counts.chapters_worked_on || 
                                CASE WHEN :chapter_id IS NOT NULL THEN ARRAY[:chapter_id] ELSE ARRAY[]::INTEGER[] END) elem
                )
        """),
        {"series_id": session.series_id, "words": session.words_written, "chapter_id": session.chapter_id}
    )
    await db.commit()
    
    return {"id": row.id, "message": "Writing session logged successfully"}


# ============================================================================
# DAILY WORD COUNTS
# ============================================================================

@router.get("/goals/daily/{series_id}")
async def get_daily_word_counts(
    series_id: int,
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Get daily word counts for a series."""
    result = await db.execute(
        text("""
            SELECT * FROM daily_word_counts
            WHERE series_id = :series_id
            AND count_date >= CURRENT_DATE - :days
            ORDER BY count_date DESC
        """),
        {"series_id": series_id, "days": days}
    )
    counts = result.fetchall()
    return [
        {
            "date": c.count_date.isoformat() if c.count_date else None,
            "words_added": c.words_added,
            "words_deleted": c.words_deleted,
            "net_words": c.net_words,
            "chapters_worked_on": c.chapters_worked_on or []
        }
        for c in counts
    ]


@router.post("/goals/daily")
async def update_daily_word_count(
    update: DailyWordCountUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update daily word count (call when editing chapters)."""
    net = update.words_added - update.words_deleted
    
    await db.execute(
        text("""
            INSERT INTO daily_word_counts (series_id, count_date, words_added, words_deleted, net_words, chapters_worked_on)
            VALUES (:series_id, CURRENT_DATE, :words_added, :words_deleted, :net,
                    CASE WHEN :chapter_id IS NOT NULL THEN ARRAY[:chapter_id] ELSE ARRAY[]::INTEGER[] END)
            ON CONFLICT (series_id, count_date) DO UPDATE
            SET words_added = daily_word_counts.words_added + :words_added,
                words_deleted = daily_word_counts.words_deleted + :words_deleted,
                net_words = daily_word_counts.net_words + :net,
                chapters_worked_on = (
                    SELECT array_agg(DISTINCT elem)
                    FROM unnest(daily_word_counts.chapters_worked_on || 
                                CASE WHEN :chapter_id IS NOT NULL THEN ARRAY[:chapter_id] ELSE ARRAY[]::INTEGER[] END) elem
                )
        """),
        {
            "series_id": update.series_id,
            "words_added": update.words_added,
            "words_deleted": update.words_deleted,
            "net": net,
            "chapter_id": update.chapter_id
        }
    )
    await db.commit()
    
    return {"message": "Daily word count updated"}


# ============================================================================
# PROGRESS & STATISTICS
# ============================================================================

@router.get("/goals/progress/{series_id}")
async def get_writing_progress(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get comprehensive writing progress for a series."""
    # Get active goals
    goals_result = await db.execute(
        text("SELECT * FROM writing_goals WHERE series_id = :id AND is_active = TRUE"),
        {"id": series_id}
    )
    goals = goals_result.fetchall()
    
    # Get today's progress
    today_result = await db.execute(
        text("SELECT * FROM daily_word_counts WHERE series_id = :id AND count_date = CURRENT_DATE"),
        {"id": series_id}
    )
    today = today_result.fetchone()
    
    # Get this week's progress
    week_result = await db.execute(
        text("""
            SELECT SUM(net_words) as total
            FROM daily_word_counts
            WHERE series_id = :id
            AND count_date >= date_trunc('week', CURRENT_DATE)
        """),
        {"id": series_id}
    )
    week = week_result.fetchone()
    
    # Get this month's progress
    month_result = await db.execute(
        text("""
            SELECT SUM(net_words) as total
            FROM daily_word_counts
            WHERE series_id = :id
            AND count_date >= date_trunc('month', CURRENT_DATE)
        """),
        {"id": series_id}
    )
    month = month_result.fetchone()
    
    # Get total series word count
    total_result = await db.execute(
        text("""
            SELECT SUM(c.word_count) as total
            FROM chapters c
            JOIN books b ON c.book_id = b.id
            WHERE b.series_id = :id
        """),
        {"id": series_id}
    )
    total = total_result.fetchone()
    
    # Get streak (consecutive days with writing)
    streak_result = await db.execute(
        text("""
            WITH dates AS (
                SELECT count_date, ROW_NUMBER() OVER (ORDER BY count_date DESC) as rn
                FROM daily_word_counts
                WHERE series_id = :id AND net_words > 0
                ORDER BY count_date DESC
            )
            SELECT COUNT(*) as streak
            FROM dates
            WHERE count_date = CURRENT_DATE - (rn - 1)
        """),
        {"id": series_id}
    )
    streak = streak_result.fetchone()
    
    # Build progress report for each goal
    goal_progress = []
    for g in goals:
        progress = {
            "goal_id": g.id,
            "goal_type": g.goal_type,
            "target_words": g.target_words,
            "target_chapters": g.target_chapters,
            "deadline": g.deadline.isoformat() if g.deadline else None
        }
        
        if g.goal_type == "daily":
            progress["current"] = today.net_words if today else 0
            progress["percentage"] = round((progress["current"] / g.target_words * 100) if g.target_words else 0, 1)
        elif g.goal_type == "weekly":
            progress["current"] = week.total if week and week.total else 0
            progress["percentage"] = round((progress["current"] / g.target_words * 100) if g.target_words else 0, 1)
        elif g.goal_type == "monthly":
            progress["current"] = month.total if month and month.total else 0
            progress["percentage"] = round((progress["current"] / g.target_words * 100) if g.target_words else 0, 1)
        elif g.goal_type == "total":
            progress["current"] = total.total if total and total.total else 0
            progress["percentage"] = round((progress["current"] / g.target_words * 100) if g.target_words else 0, 1)
        
        goal_progress.append(progress)
    
    return {
        "today": {
            "words_added": today.words_added if today else 0,
            "words_deleted": today.words_deleted if today else 0,
            "net_words": today.net_words if today else 0
        },
        "this_week": week.total if week and week.total else 0,
        "this_month": month.total if month and month.total else 0,
        "total_words": total.total if total and total.total else 0,
        "streak_days": streak.streak if streak else 0,
        "goals": goal_progress
    }





