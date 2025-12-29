"""Plot Lab API endpoints - Beat sheets, plot structure, what-if analysis."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel
import json

from app.database.postgres import get_db
from app.services.llm_service import get_llm_service

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class PlotTemplate(BaseModel):
    id: int
    name: str
    description: Optional[str]
    beat_count: int
    structure: list
    genre_tags: Optional[List[str]]

class PlotBeatCreate(BaseModel):
    series_id: int
    book_id: Optional[int]
    template_id: Optional[int]
    beat_name: str
    beat_description: Optional[str]
    target_chapter: Optional[int]
    order_index: int
    notes: Optional[str]

class PlotBeatUpdate(BaseModel):
    beat_name: Optional[str]
    beat_description: Optional[str]
    target_chapter: Optional[int]
    actual_chapter_id: Optional[int]
    status: Optional[str]
    notes: Optional[str]

class PlotVariationCreate(BaseModel):
    series_id: int
    source_chapter_id: Optional[int]
    variation_title: str
    what_if_premise: str

class GenerateBeatSheetRequest(BaseModel):
    series_id: int
    book_id: Optional[int]
    template_name: str = "Three-Act Structure"
    story_premise: Optional[str]
    genre: Optional[str]


# ============================================================================
# PLOT TEMPLATES
# ============================================================================

@router.get("/plot/templates")
async def list_plot_templates(db: AsyncSession = Depends(get_db)):
    """Get all available plot templates."""
    result = await db.execute(
        text("SELECT * FROM plot_templates ORDER BY name")
    )
    templates = result.fetchall()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "beat_count": t.beat_count,
            "structure": t.structure,
            "genre_tags": t.genre_tags or []
        }
        for t in templates
    ]


# ============================================================================
# PLOT BEATS
# ============================================================================

@router.get("/plot/beats/{series_id}")
async def get_plot_beats(
    series_id: int,
    book_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get plot beats for a series or specific book."""
    if book_id:
        result = await db.execute(
            text("""
                SELECT pb.*, c.title as chapter_title
                FROM plot_beats pb
                LEFT JOIN chapters c ON pb.actual_chapter_id = c.id
                WHERE pb.series_id = :series_id AND pb.book_id = :book_id
                ORDER BY pb.order_index
            """),
            {"series_id": series_id, "book_id": book_id}
        )
    else:
        result = await db.execute(
            text("""
                SELECT pb.*, c.title as chapter_title
                FROM plot_beats pb
                LEFT JOIN chapters c ON pb.actual_chapter_id = c.id
                WHERE pb.series_id = :series_id
                ORDER BY pb.book_id NULLS FIRST, pb.order_index
            """),
            {"series_id": series_id}
        )
    
    beats = result.fetchall()
    return [
        {
            "id": b.id,
            "series_id": b.series_id,
            "book_id": b.book_id,
            "template_id": b.template_id,
            "beat_name": b.beat_name,
            "beat_description": b.beat_description,
            "target_chapter": b.target_chapter,
            "actual_chapter_id": b.actual_chapter_id,
            "chapter_title": b.chapter_title,
            "order_index": b.order_index,
            "status": b.status,
            "notes": b.notes,
            "ai_suggestions": b.ai_suggestions
        }
        for b in beats
    ]


@router.post("/plot/beats")
async def create_plot_beat(
    beat: PlotBeatCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new plot beat."""
    result = await db.execute(
        text("""
            INSERT INTO plot_beats (series_id, book_id, template_id, beat_name, 
                                    beat_description, target_chapter, order_index, notes)
            VALUES (:series_id, :book_id, :template_id, :beat_name, 
                    :beat_description, :target_chapter, :order_index, :notes)
            RETURNING *
        """),
        {
            "series_id": beat.series_id,
            "book_id": beat.book_id,
            "template_id": beat.template_id,
            "beat_name": beat.beat_name,
            "beat_description": beat.beat_description,
            "target_chapter": beat.target_chapter,
            "order_index": beat.order_index,
            "notes": beat.notes
        }
    )
    await db.commit()
    row = result.fetchone()
    return {"id": row.id, "message": "Plot beat created successfully"}


@router.put("/plot/beats/{beat_id}")
async def update_plot_beat(
    beat_id: int,
    beat: PlotBeatUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a plot beat."""
    updates = []
    params = {"beat_id": beat_id}
    
    if beat.beat_name is not None:
        updates.append("beat_name = :beat_name")
        params["beat_name"] = beat.beat_name
    if beat.beat_description is not None:
        updates.append("beat_description = :beat_description")
        params["beat_description"] = beat.beat_description
    if beat.target_chapter is not None:
        updates.append("target_chapter = :target_chapter")
        params["target_chapter"] = beat.target_chapter
    if beat.actual_chapter_id is not None:
        updates.append("actual_chapter_id = :actual_chapter_id")
        params["actual_chapter_id"] = beat.actual_chapter_id
    if beat.status is not None:
        updates.append("status = :status")
        params["status"] = beat.status
    if beat.notes is not None:
        updates.append("notes = :notes")
        params["notes"] = beat.notes
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    updates.append("updated_at = NOW()")
    
    result = await db.execute(
        text(f"UPDATE plot_beats SET {', '.join(updates)} WHERE id = :beat_id RETURNING *"),
        params
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Beat not found")
    
    return {"message": "Plot beat updated successfully"}


@router.delete("/plot/beats/{beat_id}")
async def delete_plot_beat(beat_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a plot beat."""
    result = await db.execute(
        text("DELETE FROM plot_beats WHERE id = :beat_id RETURNING id"),
        {"beat_id": beat_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Beat not found")
    
    return {"message": "Plot beat deleted successfully"}


# ============================================================================
# AI-POWERED BEAT SHEET GENERATION
# ============================================================================

@router.post("/plot/generate-beat-sheet")
async def generate_beat_sheet(
    request: GenerateBeatSheetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate a beat sheet using AI based on template and story info."""
    # Get template
    template_result = await db.execute(
        text("SELECT * FROM plot_templates WHERE name = :name"),
        {"name": request.template_name}
    )
    template = template_result.fetchone()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Get series info
    series_result = await db.execute(
        text("SELECT * FROM series WHERE id = :id"),
        {"id": request.series_id}
    )
    series = series_result.fetchone()
    
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    
    # Generate beats using LLM
    llm = get_llm_service()
    
    prompt = f"""Generate a detailed beat sheet for a story using the {template.name} structure.

Story Details:
- Title: {series.title}
- Premise: {request.story_premise or series.premise or 'Not provided'}
- Genre: {request.genre or 'General fiction'}
- Themes: {', '.join(series.themes) if series.themes else 'Not specified'}

Template Structure:
{json.dumps(template.structure, indent=2)}

For each beat in the template, provide:
1. A specific description of what happens at this beat for THIS story
2. Any notes or suggestions

Return as JSON array with format:
[
  {{"beat_name": "...", "beat_description": "Specific description for this story", "notes": "Suggestions"}},
  ...
]

Generate creative, story-specific content for each beat."""

    try:
        response = await llm.generate([
            {"role": "system", "content": "You are a story structure expert. Generate detailed beat sheets in JSON format."},
            {"role": "user", "content": prompt}
        ], temperature=0.7)
        
        # Parse response and create beats
        import re
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            beats_data = json.loads(json_match.group())
            
            # Insert beats into database
            created_beats = []
            for idx, beat_data in enumerate(beats_data):
                result = await db.execute(
                    text("""
                        INSERT INTO plot_beats (series_id, book_id, template_id, beat_name,
                                               beat_description, order_index, ai_suggestions)
                        VALUES (:series_id, :book_id, :template_id, :beat_name,
                                :beat_description, :order_index, :ai_suggestions)
                        RETURNING id
                    """),
                    {
                        "series_id": request.series_id,
                        "book_id": request.book_id,
                        "template_id": template.id,
                        "beat_name": beat_data.get("beat_name", f"Beat {idx+1}"),
                        "beat_description": beat_data.get("beat_description", ""),
                        "order_index": idx,
                        "ai_suggestions": beat_data.get("notes", "")
                    }
                )
                row = result.fetchone()
                created_beats.append(row.id)
            
            await db.commit()
            return {
                "message": f"Generated {len(created_beats)} beats",
                "beat_ids": created_beats,
                "template_used": template.name
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to parse AI response")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


# ============================================================================
# WHAT-IF ANALYSIS
# ============================================================================

@router.get("/plot/variations/{series_id}")
async def get_plot_variations(series_id: int, db: AsyncSession = Depends(get_db)):
    """Get all what-if variations for a series."""
    result = await db.execute(
        text("""
            SELECT pv.*, c.title as source_chapter_title
            FROM plot_variations pv
            LEFT JOIN chapters c ON pv.source_chapter_id = c.id
            WHERE pv.series_id = :series_id
            ORDER BY pv.created_at DESC
        """),
        {"series_id": series_id}
    )
    variations = result.fetchall()
    return [
        {
            "id": v.id,
            "series_id": v.series_id,
            "source_chapter_id": v.source_chapter_id,
            "source_chapter_title": v.source_chapter_title,
            "variation_title": v.variation_title,
            "what_if_premise": v.what_if_premise,
            "ai_analysis": v.ai_analysis,
            "consequences": v.consequences,
            "is_explored": v.is_explored,
            "exploration_notes": v.exploration_notes,
            "created_at": v.created_at.isoformat() if v.created_at else None
        }
        for v in variations
    ]


@router.post("/plot/what-if")
async def create_what_if_analysis(
    variation: PlotVariationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a what-if analysis with AI-generated consequences."""
    # Get story context
    context_result = await db.execute(
        text("""
            SELECT s.title, s.premise, s.themes,
                   (SELECT json_agg(json_build_object('name', cp.name, 'description', cp.description))
                    FROM character_profiles cp WHERE cp.series_id = s.id) as characters,
                   (SELECT json_agg(json_build_object('title', f.title, 'status', f.status))
                    FROM foreshadowing f WHERE f.series_id = s.id) as foreshadowing
            FROM series s WHERE s.id = :series_id
        """),
        {"series_id": variation.series_id}
    )
    context = context_result.fetchone()
    
    if not context:
        raise HTTPException(status_code=404, detail="Series not found")
    
    # Generate analysis using LLM
    llm = get_llm_service()
    
    prompt = f"""Analyze the consequences of a "What If" scenario in this story:

Story: {context.title}
Premise: {context.premise or 'Not provided'}
Themes: {', '.join(context.themes) if context.themes else 'Not specified'}

Characters: {json.dumps(context.characters) if context.characters else 'None defined'}
Foreshadowing: {json.dumps(context.foreshadowing) if context.foreshadowing else 'None defined'}

WHAT-IF SCENARIO: {variation.what_if_premise}

Analyze:
1. Immediate plot consequences
2. Character reactions and changes
3. Which foreshadowing would be affected
4. New story opportunities this creates
5. Potential problems or inconsistencies

Return as JSON:
{{
  "analysis": "Overall analysis text",
  "consequences": [
    {{"type": "plot|character|world", "description": "...", "severity": "minor|moderate|major"}}
  ]
}}"""

    try:
        response = await llm.generate([
            {"role": "system", "content": "You are a story analyst. Analyze plot variations in JSON format."},
            {"role": "user", "content": prompt}
        ], temperature=0.7)
        
        # Parse response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        analysis_data = json.loads(json_match.group()) if json_match else {"analysis": response, "consequences": []}
        
        # Save to database
        result = await db.execute(
            text("""
                INSERT INTO plot_variations (series_id, source_chapter_id, variation_title,
                                            what_if_premise, ai_analysis, consequences)
                VALUES (:series_id, :source_chapter_id, :variation_title,
                        :what_if_premise, :ai_analysis, :consequences)
                RETURNING *
            """),
            {
                "series_id": variation.series_id,
                "source_chapter_id": variation.source_chapter_id,
                "variation_title": variation.variation_title,
                "what_if_premise": variation.what_if_premise,
                "ai_analysis": analysis_data.get("analysis", ""),
                "consequences": json.dumps(analysis_data.get("consequences", []))
            }
        )
        await db.commit()
        row = result.fetchone()
        
        return {
            "id": row.id,
            "analysis": analysis_data.get("analysis"),
            "consequences": analysis_data.get("consequences", [])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.delete("/plot/variations/{variation_id}")
async def delete_variation(variation_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a what-if variation."""
    result = await db.execute(
        text("DELETE FROM plot_variations WHERE id = :id RETURNING id"),
        {"id": variation_id}
    )
    await db.commit()
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Variation not found")
    
    return {"message": "Variation deleted successfully"}

