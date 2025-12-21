"""
Verification Hub API

Endpoints for reviewing and approving auto-extracted story elements.
All auto-extracted items start as 'pending' and must be approved here
before they're used in RAG context.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import json

from app.database.postgres import get_db

router = APIRouter(prefix="/verification", tags=["Verification Hub"])


# ============================================================
# Response Models
# ============================================================

class PendingItem(BaseModel):
    id: int
    item_type: str  # character, world_rule, foreshadowing, payoff, fact
    name: str
    description: str
    confidence: Optional[float] = None
    source: Optional[str] = None
    created_at: datetime
    details: dict


class VerificationAction(BaseModel):
    action: str  # approve, reject, edit_and_approve
    edited_data: Optional[dict] = None  # For edit_and_approve


class VerificationStats(BaseModel):
    total_pending: int
    characters: int
    world_rules: int
    foreshadowing: int
    payoffs: int
    facts: int


# ============================================================
# Get Pending Items
# ============================================================

@router.get("/stats/{series_id}", response_model=VerificationStats)
async def get_verification_stats(
    series_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get count of pending items by type for a series."""
    
    # Count characters
    chars = await db.execute(
        text("""
            SELECT COUNT(*) FROM character_profiles 
            WHERE series_id = :sid AND verification_status = 'pending'
        """),
        {"sid": series_id}
    )
    char_count = chars.scalar() or 0
    
    # Count world rules
    rules = await db.execute(
        text("""
            SELECT COUNT(*) FROM world_rules 
            WHERE series_id = :sid AND verification_status = 'pending'
        """),
        {"sid": series_id}
    )
    rule_count = rules.scalar() or 0
    
    # Count foreshadowing
    fs = await db.execute(
        text("""
            SELECT COUNT(*) FROM foreshadowing 
            WHERE series_id = :sid AND verification_status = 'pending'
        """),
        {"sid": series_id}
    )
    fs_count = fs.scalar() or 0
    
    # Count pending payoffs (from story_analyses)
    payoffs = await db.execute(
        text("""
            SELECT COUNT(*) FROM story_analyses 
            WHERE series_id = :sid AND analysis_type = 'pending_payoff'
        """),
        {"sid": series_id}
    )
    payoff_count = payoffs.scalar() or 0
    
    # Count facts
    facts = await db.execute(
        text("""
            SELECT COUNT(*) FROM story_facts 
            WHERE series_id = :sid AND verification_status = 'pending'
        """),
        {"sid": series_id}
    )
    fact_count = facts.scalar() or 0
    
    total = char_count + rule_count + fs_count + payoff_count + fact_count
    
    return VerificationStats(
        total_pending=total,
        characters=char_count,
        world_rules=rule_count,
        foreshadowing=fs_count,
        payoffs=payoff_count,
        facts=fact_count
    )


@router.get("/pending/{series_id}", response_model=List[PendingItem])
async def list_pending_items(
    series_id: int,
    item_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all pending items for verification."""
    items = []
    
    # Characters
    if not item_type or item_type == "character":
        result = await db.execute(
            text("""
                SELECT id, name, description, personality, appearance,
                       first_appearance_book, first_appearance_chapter,
                       extraction_source, created_at
                FROM character_profiles
                WHERE series_id = :sid AND verification_status = 'pending'
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"sid": series_id, "limit": limit}
        )
        for row in result.fetchall():
            items.append(PendingItem(
                id=row.id,
                item_type="character",
                name=row.name,
                description=row.description or "No description",
                source=row.extraction_source,
                created_at=row.created_at,
                details={
                    "personality": row.personality,
                    "appearance": row.appearance,
                    "first_book": row.first_appearance_book,
                    "first_chapter": row.first_appearance_chapter
                }
            ))
    
    # World Rules
    if not item_type or item_type == "world_rule":
        result = await db.execute(
            text("""
                SELECT id, rule_name, rule_description, rule_category,
                       source_book, source_chapter, source_text,
                       is_hard_rule, extraction_confidence, created_at
                FROM world_rules
                WHERE series_id = :sid AND verification_status = 'pending'
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"sid": series_id, "limit": limit}
        )
        for row in result.fetchall():
            items.append(PendingItem(
                id=row.id,
                item_type="world_rule",
                name=row.rule_name,
                description=row.rule_description,
                confidence=row.extraction_confidence,
                source=f"Book {row.source_book}, Ch {row.source_chapter}",
                created_at=row.created_at,
                details={
                    "category": row.rule_category,
                    "source_text": row.source_text,
                    "is_hard_rule": row.is_hard_rule
                }
            ))
    
    # Foreshadowing
    if not item_type or item_type == "foreshadowing":
        result = await db.execute(
            text("""
                SELECT id, title, planted_text, seed_type, subtlety,
                       intended_payoff, planted_book, planted_chapter,
                       extraction_confidence, created_at
                FROM foreshadowing
                WHERE series_id = :sid AND verification_status = 'pending'
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"sid": series_id, "limit": limit}
        )
        for row in result.fetchall():
            items.append(PendingItem(
                id=row.id,
                item_type="foreshadowing",
                name=row.title,
                description=row.planted_text,
                confidence=row.extraction_confidence,
                source=f"Book {row.planted_book}, Ch {row.planted_chapter}",
                created_at=row.created_at,
                details={
                    "seed_type": row.seed_type,
                    "subtlety": row.subtlety,
                    "intended_payoff": row.intended_payoff
                }
            ))
    
    # Payoffs (from story_analyses)
    if not item_type or item_type == "payoff":
        result = await db.execute(
            text("""
                SELECT sa.id, sa.query, sa.analysis_result, sa.metadata, sa.created_at,
                       f.title as seed_title
                FROM story_analyses sa
                LEFT JOIN foreshadowing f ON (sa.metadata->>'seed_id')::int = f.id
                WHERE sa.series_id = :sid AND sa.analysis_type = 'pending_payoff'
                ORDER BY sa.created_at DESC
                LIMIT :limit
            """),
            {"sid": series_id, "limit": limit}
        )
        for row in result.fetchall():
            meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or '{}')
            items.append(PendingItem(
                id=row.id,
                item_type="payoff",
                name=f"Payoff: {row.seed_title or 'Unknown Seed'}",
                description=row.analysis_result or "",
                confidence=meta.get("confidence"),
                source=f"Chapter {meta.get('payoff_chapter')}",
                created_at=row.created_at,
                details={
                    "seed_id": meta.get("seed_id"),
                    "payoff_chapter": meta.get("payoff_chapter"),
                    "seed_title": row.seed_title
                }
            ))
    
    # Story Facts
    if not item_type or item_type == "fact":
        result = await db.execute(
            text("""
                SELECT id, fact_description, fact_category,
                       established_in_chapter, is_secret, importance, created_at
                FROM story_facts
                WHERE series_id = :sid AND verification_status = 'pending'
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"sid": series_id, "limit": limit}
        )
        for row in result.fetchall():
            items.append(PendingItem(
                id=row.id,
                item_type="fact",
                name=f"[{row.fact_category}] Fact",
                description=row.fact_description,
                source=f"Chapter {row.established_in_chapter}",
                created_at=row.created_at,
                details={
                    "category": row.fact_category,
                    "is_secret": row.is_secret,
                    "importance": row.importance
                }
            ))
    
    # Sort all by created_at desc
    items.sort(key=lambda x: x.created_at, reverse=True)
    return items[:limit]


# ============================================================
# Verify Individual Items
# ============================================================

@router.post("/character/{item_id}")
async def verify_character(
    item_id: int,
    action: VerificationAction,
    db: AsyncSession = Depends(get_db)
):
    """Approve, reject, or edit a pending character."""
    
    if action.action == "reject":
        await db.execute(
            text("UPDATE character_profiles SET verification_status = 'rejected' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "approve":
        await db.execute(
            text("UPDATE character_profiles SET verification_status = 'approved' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "edit_and_approve" and action.edited_data:
        data = action.edited_data
        await db.execute(
            text("""
                UPDATE character_profiles SET
                    name = COALESCE(:name, name),
                    description = COALESCE(:description, description),
                    personality = COALESCE(:personality, personality),
                    appearance = COALESCE(:appearance, appearance),
                    verification_status = 'approved'
                WHERE id = :id
            """),
            {
                "id": item_id,
                "name": data.get("name"),
                "description": data.get("description"),
                "personality": data.get("personality"),
                "appearance": data.get("appearance")
            }
        )
    
    await db.commit()
    return {"status": "ok", "action": action.action}


@router.post("/world_rule/{item_id}")
async def verify_world_rule(
    item_id: int,
    action: VerificationAction,
    db: AsyncSession = Depends(get_db)
):
    """Approve, reject, or edit a pending world rule."""
    
    if action.action == "reject":
        await db.execute(
            text("UPDATE world_rules SET verification_status = 'rejected' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "approve":
        await db.execute(
            text("UPDATE world_rules SET verification_status = 'approved' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "edit_and_approve" and action.edited_data:
        data = action.edited_data
        await db.execute(
            text("""
                UPDATE world_rules SET
                    rule_name = COALESCE(:name, rule_name),
                    rule_description = COALESCE(:description, rule_description),
                    rule_category = COALESCE(:category, rule_category),
                    is_hard_rule = COALESCE(:is_hard, is_hard_rule),
                    verification_status = 'approved'
                WHERE id = :id
            """),
            {
                "id": item_id,
                "name": data.get("name"),
                "description": data.get("description"),
                "category": data.get("category"),
                "is_hard": data.get("is_hard_rule")
            }
        )
    
    await db.commit()
    return {"status": "ok", "action": action.action}


@router.post("/foreshadowing/{item_id}")
async def verify_foreshadowing(
    item_id: int,
    action: VerificationAction,
    db: AsyncSession = Depends(get_db)
):
    """Approve, reject, or edit a pending foreshadowing seed."""
    
    if action.action == "reject":
        await db.execute(
            text("UPDATE foreshadowing SET verification_status = 'rejected' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "approve":
        await db.execute(
            text("UPDATE foreshadowing SET verification_status = 'approved' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "edit_and_approve" and action.edited_data:
        data = action.edited_data
        await db.execute(
            text("""
                UPDATE foreshadowing SET
                    title = COALESCE(:title, title),
                    planted_text = COALESCE(:planted_text, planted_text),
                    seed_type = COALESCE(:seed_type, seed_type),
                    subtlety = COALESCE(:subtlety, subtlety),
                    intended_payoff = COALESCE(:payoff, intended_payoff),
                    verification_status = 'approved'
                WHERE id = :id
            """),
            {
                "id": item_id,
                "title": data.get("title"),
                "planted_text": data.get("planted_text"),
                "seed_type": data.get("seed_type"),
                "subtlety": data.get("subtlety"),
                "payoff": data.get("intended_payoff")
            }
        )
    
    await db.commit()
    return {"status": "ok", "action": action.action}


@router.post("/payoff/{item_id}")
async def verify_payoff(
    item_id: int,
    action: VerificationAction,
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject a detected payoff."""
    
    # First get the payoff details
    result = await db.execute(
        text("SELECT metadata, analysis_result FROM story_analyses WHERE id = :id"),
        {"id": item_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Payoff not found")
    
    meta = row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or '{}')
    
    if action.action == "reject":
        # Just delete the analysis record
        await db.execute(
            text("DELETE FROM story_analyses WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action in ("approve", "edit_and_approve"):
        seed_id = meta.get("seed_id")
        payoff_chapter = meta.get("payoff_chapter")
        payoff_text = row.analysis_result
        
        if action.edited_data:
            payoff_text = action.edited_data.get("payoff_text", payoff_text)
            payoff_chapter = action.edited_data.get("payoff_chapter", payoff_chapter)
        
        # Update the actual foreshadowing record
        await db.execute(
            text("""
                UPDATE foreshadowing SET
                    payoff_chapter = :chapter,
                    payoff_text = :text,
                    status = 'paid_off',
                    updated_at = NOW()
                WHERE id = :id
            """),
            {
                "id": seed_id,
                "chapter": payoff_chapter,
                "text": payoff_text
            }
        )
        
        # Delete the analysis record
        await db.execute(
            text("DELETE FROM story_analyses WHERE id = :id"),
            {"id": item_id}
        )
    
    await db.commit()
    return {"status": "ok", "action": action.action}


@router.post("/fact/{item_id}")
async def verify_fact(
    item_id: int,
    action: VerificationAction,
    db: AsyncSession = Depends(get_db)
):
    """Approve, reject, or edit a pending story fact."""
    
    if action.action == "reject":
        await db.execute(
            text("UPDATE story_facts SET verification_status = 'rejected' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "approve":
        await db.execute(
            text("UPDATE story_facts SET verification_status = 'approved' WHERE id = :id"),
            {"id": item_id}
        )
    elif action.action == "edit_and_approve" and action.edited_data:
        data = action.edited_data
        await db.execute(
            text("""
                UPDATE story_facts SET
                    fact_description = COALESCE(:description, fact_description),
                    fact_category = COALESCE(:category, fact_category),
                    is_secret = COALESCE(:is_secret, is_secret),
                    importance = COALESCE(:importance, importance),
                    verification_status = 'approved'
                WHERE id = :id
            """),
            {
                "id": item_id,
                "description": data.get("description"),
                "category": data.get("category"),
                "is_secret": data.get("is_secret"),
                "importance": data.get("importance")
            }
        )
    
    await db.commit()
    return {"status": "ok", "action": action.action}


# ============================================================
# Bulk Actions
# ============================================================

class BulkVerification(BaseModel):
    item_ids: List[int]
    item_type: str
    action: str  # approve, reject


@router.post("/bulk")
async def bulk_verify(
    bulk: BulkVerification,
    db: AsyncSession = Depends(get_db)
):
    """Approve or reject multiple items at once."""
    
    new_status = "approved" if bulk.action == "approve" else "rejected"
    
    table_map = {
        "character": "character_profiles",
        "world_rule": "world_rules",
        "foreshadowing": "foreshadowing",
        "fact": "story_facts"
    }
    
    if bulk.item_type == "payoff":
        # Payoffs are handled differently
        if bulk.action == "reject":
            for item_id in bulk.item_ids:
                await db.execute(
                    text("DELETE FROM story_analyses WHERE id = :id"),
                    {"id": item_id}
                )
        else:
            # For bulk approve of payoffs, we'd need to update each seed
            # This is complex, so we'll just skip it and require individual approval
            raise HTTPException(
                status_code=400,
                detail="Bulk approval of payoffs not supported. Please approve individually."
            )
    else:
        table = table_map.get(bulk.item_type)
        if not table:
            raise HTTPException(status_code=400, detail=f"Unknown item type: {bulk.item_type}")
        
        # Use parameterized IDs
        for item_id in bulk.item_ids:
            await db.execute(
                text(f"UPDATE {table} SET verification_status = :status WHERE id = :id"),
                {"status": new_status, "id": item_id}
            )
    
    await db.commit()
    return {"status": "ok", "updated": len(bulk.item_ids)}

