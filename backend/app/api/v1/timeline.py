"""Timeline API endpoints - Story event timeline management."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel

from app.database.postgres import get_db

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TimelineEventCreate(BaseModel):
    series_id: int
    event_name: str
    event_description: Optional[str]
    story_date: Optional[str]
    story_date_sortable: Optional[int]
    chapter_id: Optional[int]
    character_ids: Optional[List[int]]
    location: Optional[str]
    event_type: str = "plot"
    importance: str = "normal"

class TimelineEventUpdate(BaseModel):
    event_name: Optional[str]
    event_description: Optional[str]
    story_date: Optional[str]
    story_date_sortable: Optional[int]
    chapter_id: Optional[int]
    character_ids: Optional[List[int]]
    location: Optional[str]
    event_type: Optional[str]
    importance: Optional[str]

class TimelineTrackCreate(BaseModel):
    series_id: int
    track_name: str
    track_color: str = "#8b5cf6"
    character_id: Optional[int]
    is_main_track: bool = False


# ============================================================================
# TIMELINE EVENTS
# ============================================================================

@router.get("/timeline/{series_id}")
async def get_timeline(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get all timeline events for a series."""
    result = await db.execute(
        text("""
            SELECT te.*, c.title as chapter_title,
                   array_agg(DISTINCT cp.name) FILTER (WHERE cp.name IS NOT NULL) as character_names
            FROM timeline_events te
            LEFT JOIN chapters c ON te.chapter_id = c.id
            LEFT JOIN character_profiles cp ON cp.id = ANY(te.character_ids)
            WHERE te.series_id = :series_id
            GROUP BY te.id, c.title
            ORDER BY te.story_date_sortable NULLS LAST, te.created_at
        """),
        {"series_id": series_id}
    )
    events = result.fetchall()
    return [
        {
            "id": e.id,
            "series_id": e.series_id,
            "event_name": e.event_name,
            "event_description": e.event_description,
            "story_date": e.story_date,
            "story_date_sortable": e.story_date_sortable,
            "chapter_id": e.chapter_id,
            "chapter_title": e.chapter_title,
            "character_ids": e.character_ids or [],
            "character_names": e.character_names or [],
            "location": e.location,
            "event_type": e.event_type,
            "importance": e.importance,
            "created_at": e.created_at.isoformat() if e.created_at else None
        }
        for e in events
    ]


@router.post("/timeline/events")
async def create_timeline_event(
    event: TimelineEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new timeline event."""
    result = await db.execute(
        text("""
            INSERT INTO timeline_events (series_id, event_name, event_description,
                                         story_date, story_date_sortable, chapter_id,
                                         character_ids, location, event_type, importance)
            VALUES (:series_id, :event_name, :event_description,
                    :story_date, :story_date_sortable, :chapter_id,
                    :character_ids, :location, :event_type, :importance)
            RETURNING *
        """),
        {
            "series_id": event.series_id,
            "event_name": event.event_name,
            "event_description": event.event_description,
            "story_date": event.story_date,
            "story_date_sortable": event.story_date_sortable,
            "chapter_id": event.chapter_id,
            "character_ids": event.character_ids,
            "location": event.location,
            "event_type": event.event_type,
            "importance": event.importance
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Timeline event created successfully"}


@router.put("/timeline/events/{event_id}")
async def update_timeline_event(
    event_id: int,
    event: TimelineEventUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a timeline event."""
    updates = []
    params = {"event_id": event_id}
    
    for field in ["event_name", "event_description", "story_date", 
                  "story_date_sortable", "chapter_id", "character_ids",
                  "location", "event_type", "importance"]:
        value = getattr(event, field)
        if value is not None:
            updates.append(f"{field} = :{field}")
            params[field] = value
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    updates.append("updated_at = NOW()")
    
    result = await db.execute(
        text(f"UPDATE timeline_events SET {', '.join(updates)} WHERE id = :event_id RETURNING *"),
        params
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {"message": "Timeline event updated successfully"}


@router.delete("/timeline/events/{event_id}")
async def delete_timeline_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a timeline event."""
    result = await db.execute(
        text("DELETE FROM timeline_events WHERE id = :event_id RETURNING id"),
        {"event_id": event_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {"message": "Timeline event deleted successfully"}


# ============================================================================
# TIMELINE TRACKS
# ============================================================================

@router.get("/timeline/tracks/{series_id}")
async def get_timeline_tracks(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get all timeline tracks for a series."""
    result = await db.execute(
        text("""
            SELECT tt.*, cp.name as character_name
            FROM timeline_tracks tt
            LEFT JOIN character_profiles cp ON tt.character_id = cp.id
            WHERE tt.series_id = :series_id
            ORDER BY tt.is_main_track DESC, tt.order_index
        """),
        {"series_id": series_id}
    )
    tracks = result.fetchall()
    return [
        {
            "id": t.id,
            "series_id": t.series_id,
            "track_name": t.track_name,
            "track_color": t.track_color,
            "character_id": t.character_id,
            "character_name": t.character_name,
            "is_main_track": t.is_main_track,
            "order_index": t.order_index
        }
        for t in tracks
    ]


@router.post("/timeline/tracks")
async def create_timeline_track(
    track: TimelineTrackCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new timeline track."""
    # Get max order_index
    max_result = await db.execute(
        text("SELECT COALESCE(MAX(order_index), -1) + 1 as next_idx FROM timeline_tracks WHERE series_id = :series_id"),
        {"series_id": track.series_id}
    )
    next_idx = max_result.fetchone().next_idx
    
    result = await db.execute(
        text("""
            INSERT INTO timeline_tracks (series_id, track_name, track_color,
                                         character_id, is_main_track, order_index)
            VALUES (:series_id, :track_name, :track_color,
                    :character_id, :is_main_track, :order_index)
            RETURNING *
        """),
        {
            "series_id": track.series_id,
            "track_name": track.track_name,
            "track_color": track.track_color,
            "character_id": track.character_id,
            "is_main_track": track.is_main_track,
            "order_index": next_idx
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Timeline track created successfully"}


@router.delete("/timeline/tracks/{track_id}")
async def delete_timeline_track(track_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a timeline track."""
    result = await db.execute(
        text("DELETE FROM timeline_tracks WHERE id = :track_id RETURNING id"),
        {"track_id": track_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Track not found")
    
    return {"message": "Timeline track deleted successfully"}


# ============================================================================
# TIMELINE ANALYSIS
# ============================================================================

@router.get("/timeline/gaps/{series_id}")
async def find_timeline_gaps(series_id: int, db: AsyncSession = Depends(get_db)):
    """Find gaps in the timeline where no events are recorded."""
    # Get all events sorted by date
    result = await db.execute(
        text("""
            SELECT story_date, story_date_sortable, event_name
            FROM timeline_events
            WHERE series_id = :series_id AND story_date_sortable IS NOT NULL
            ORDER BY story_date_sortable
        """),
        {"series_id": series_id}
    )
    events = result.fetchall()
    
    gaps = []
    for i in range(len(events) - 1):
        current = events[i]
        next_event = events[i + 1]
        gap = next_event.story_date_sortable - current.story_date_sortable
        
        # Flag gaps larger than 30 "units" (could be days, etc.)
        if gap > 30:
            gaps.append({
                "between_events": [current.event_name, next_event.event_name],
                "gap_size": gap,
                "from_date": current.story_date,
                "to_date": next_event.story_date
            })
    
    return {"gaps": gaps, "total_events": len(events)}


