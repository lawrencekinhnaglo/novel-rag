"""Consistency Checker API - Detect inconsistencies in story content."""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from pydantic import BaseModel
from app.database.postgres import get_db
from app.services.llm_service import get_llm_service
import logging
import json
import re

logger = logging.getLogger(__name__)

router = APIRouter()


class ConsistencyCheck(BaseModel):
    """Consistency check request."""
    content: str
    check_types: List[str] = ["characters", "timeline", "worldbuilding", "continuity"]
    series_id: Optional[int] = None
    language: str = "zh-TW"


class ConsistencyIssue(BaseModel):
    """A consistency issue found."""
    type: str  # character, timeline, worldbuilding, continuity
    severity: str  # error, warning, info
    description: str
    location: Optional[str] = None
    suggestion: Optional[str] = None


class ConsistencyReport(BaseModel):
    """Full consistency report."""
    total_issues: int
    errors: int
    warnings: int
    info: int
    issues: List[ConsistencyIssue]
    checked_content_length: int


@router.post("/check", response_model=ConsistencyReport)
async def check_consistency(
    request: ConsistencyCheck,
    db: AsyncSession = Depends(get_db)
):
    """Check content for consistency issues against established worldbuilding."""
    
    issues: List[ConsistencyIssue] = []
    
    # Get established worldbuilding for comparison
    worldbuilding_context = await _get_worldbuilding_context(db, request.series_id)
    
    # Check each type
    if "characters" in request.check_types:
        char_issues = await _check_character_consistency(
            request.content, worldbuilding_context, db, request.series_id
        )
        issues.extend(char_issues)
    
    if "timeline" in request.check_types:
        timeline_issues = await _check_timeline_consistency(
            request.content, worldbuilding_context
        )
        issues.extend(timeline_issues)
    
    if "worldbuilding" in request.check_types:
        world_issues = await _check_worldbuilding_consistency(
            request.content, worldbuilding_context
        )
        issues.extend(world_issues)
    
    if "continuity" in request.check_types:
        continuity_issues = await _check_continuity(
            request.content, worldbuilding_context, request.language
        )
        issues.extend(continuity_issues)
    
    # Count by severity
    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    info = sum(1 for i in issues if i.severity == "info")
    
    return ConsistencyReport(
        total_issues=len(issues),
        errors=errors,
        warnings=warnings,
        info=info,
        issues=issues,
        checked_content_length=len(request.content)
    )


async def _get_worldbuilding_context(db: AsyncSession, series_id: Optional[int]) -> dict:
    """Get established worldbuilding data for consistency checking."""
    context = {
        "characters": [],
        "world_rules": [],
        "timeline_events": [],
        "power_system": [],
        "locations": [],
        "artifacts": []
    }
    
    try:
        # Get characters
        if series_id:
            chars_result = await db.execute(
                text("""
                    SELECT name, aliases, description, personality, role
                    FROM character_profiles
                    WHERE series_id = :series_id
                """),
                {"series_id": series_id}
            )
            for row in chars_result.fetchall():
                context["characters"].append({
                    "name": row.name,
                    "aliases": row.aliases or [],
                    "description": row.description,
                    "personality": row.personality,
                    "role": row.role
                })
        
        # Get world rules
        if series_id:
            rules_result = await db.execute(
                text("""
                    SELECT rule_name, rule_category, rule_description
                    FROM world_rules
                    WHERE series_id = :series_id
                """),
                {"series_id": series_id}
            )
            for row in rules_result.fetchall():
                context["world_rules"].append({
                    "name": row.rule_name,
                    "category": row.rule_category,
                    "description": row.rule_description
                })
        
        # Get knowledge base items
        kb_result = await db.execute(
            text("""
                SELECT title, content, category
                FROM knowledge_base
                WHERE category IN ('cultivation_realm', 'artifact', 'location', 'worldbuilding')
                LIMIT 50
            """)
        )
        for row in kb_result.fetchall():
            if row.category == 'cultivation_realm':
                context["power_system"].append({"title": row.title, "content": row.content})
            elif row.category == 'artifact':
                context["artifacts"].append({"title": row.title, "content": row.content})
            elif row.category == 'location':
                context["locations"].append({"title": row.title, "content": row.content})
                
    except Exception as e:
        logger.error(f"Failed to get worldbuilding context: {e}")
    
    return context


async def _check_character_consistency(
    content: str,
    worldbuilding: dict,
    db: AsyncSession,
    series_id: Optional[int]
) -> List[ConsistencyIssue]:
    """Check for character-related inconsistencies."""
    issues = []
    
    # Get known character names
    known_characters = {c["name"] for c in worldbuilding["characters"]}
    known_aliases = set()
    for c in worldbuilding["characters"]:
        if c.get("aliases"):
            known_aliases.update(c["aliases"])
    
    all_known = known_characters | known_aliases
    
    # Find names mentioned in content (Chinese names are usually 2-4 characters)
    # This is a simplified check - a full implementation would use NLP
    potential_names = re.findall(r'[\u4e00-\u9fff]{2,4}', content)
    
    # Check for potential unknown characters (very basic heuristic)
    # In a real implementation, you'd use NER
    common_words = {'這個', '那個', '什麼', '為什麼', '如何', '怎麼', '已經', '可以', '應該', '不是'}
    for name in set(potential_names):
        if name not in common_words and name not in all_known:
            # Check if it might be a new character
            if content.count(name) >= 3:  # Mentioned multiple times
                issues.append(ConsistencyIssue(
                    type="character",
                    severity="info",
                    description=f"'{name}' appears multiple times but is not in the character database",
                    suggestion="Consider adding this character to the database if they are a recurring character"
                ))
    
    # Check for personality/behavior consistency using LLM (if characters are established)
    if worldbuilding["characters"]:
        llm_service = get_llm_service()
        
        # Build character reference
        char_ref = "\n".join([
            f"- {c['name']}: {c.get('personality', 'Unknown personality')}"
            for c in worldbuilding["characters"][:10]
        ])
        
        try:
            prompt = f"""Analyze this text for character consistency issues. The established characters are:
{char_ref}

Text to check:
{content[:3000]}

List any instances where a character's behavior seems inconsistent with their established personality.
Return JSON array: [{{"character": "name", "issue": "description", "severity": "error|warning"}}]
Return empty array [] if no issues found."""

            response = await llm_service.generate(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse response
            try:
                # Extract JSON from response
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    llm_issues = json.loads(json_match.group())
                    for issue in llm_issues:
                        issues.append(ConsistencyIssue(
                            type="character",
                            severity=issue.get("severity", "warning"),
                            description=f"{issue.get('character', 'Character')}: {issue.get('issue', 'Behavior inconsistency')}",
                            suggestion="Review character's established personality traits"
                        ))
            except json.JSONDecodeError:
                pass  # LLM didn't return valid JSON, skip
                
        except Exception as e:
            logger.warning(f"LLM character check failed: {e}")
    
    return issues


async def _check_timeline_consistency(
    content: str,
    worldbuilding: dict
) -> List[ConsistencyIssue]:
    """Check for timeline-related inconsistencies."""
    issues = []
    
    # Look for time references
    time_patterns = [
        r'(\d+)年前',
        r'(\d+)天前',
        r'(\d+)個月',
        r'去年',
        r'明年',
        r'昨天',
        r'今天',
        r'明天'
    ]
    
    time_refs = []
    for pattern in time_patterns:
        matches = re.findall(pattern, content)
        time_refs.extend(matches)
    
    # Check for contradictory time references
    if '去年' in content and '明年' in content and '今天' not in content:
        issues.append(ConsistencyIssue(
            type="timeline",
            severity="warning",
            description="Multiple time references found (past and future) - verify timeline consistency",
            suggestion="Ensure time references are consistent within the narrative"
        ))
    
    return issues


async def _check_worldbuilding_consistency(
    content: str,
    worldbuilding: dict
) -> List[ConsistencyIssue]:
    """Check for worldbuilding rule violations."""
    issues = []
    
    # Check against established world rules
    for rule in worldbuilding["world_rules"]:
        rule_name = rule.get("name", "")
        rule_desc = rule.get("description", "")
        
        # Very basic keyword matching - a full implementation would use semantic similarity
        if rule_name and rule_name in content:
            # Found reference to a rule, could verify correct usage
            pass
    
    # Check power system consistency
    power_levels = []
    for item in worldbuilding["power_system"]:
        power_levels.append(item.get("title", ""))
    
    if power_levels:
        mentioned_levels = []
        for level in power_levels:
            if level and level in content:
                mentioned_levels.append(level)
        
        if len(mentioned_levels) > 1:
            issues.append(ConsistencyIssue(
                type="worldbuilding",
                severity="info",
                description=f"Multiple power levels mentioned: {', '.join(mentioned_levels)}",
                suggestion="Verify power progression is logical"
            ))
    
    return issues


async def _check_continuity(
    content: str,
    worldbuilding: dict,
    language: str
) -> List[ConsistencyIssue]:
    """Use LLM to check for general continuity issues."""
    issues = []
    
    llm_service = get_llm_service()
    
    # Build context summary
    context_summary = "Established worldbuilding:\n"
    if worldbuilding["world_rules"]:
        context_summary += "Rules: " + ", ".join([r["name"] for r in worldbuilding["world_rules"][:5]]) + "\n"
    if worldbuilding["characters"]:
        context_summary += "Characters: " + ", ".join([c["name"] for c in worldbuilding["characters"][:10]]) + "\n"
    
    try:
        prompt = f"""You are a continuity editor. Analyze this text for logical inconsistencies, plot holes, or continuity errors.

{context_summary}

Text to analyze:
{content[:4000]}

Look for:
1. Logical contradictions within the text
2. Events that don't follow cause-and-effect
3. Characters knowing things they shouldn't know
4. Physical impossibilities (unless explained by magic/powers)

Return JSON array: [{{"issue": "description", "severity": "error|warning|info", "location": "brief quote or null"}}]
Return empty array [] if no issues found. Be concise."""

        response = await llm_service.generate(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        
        # Parse response
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                llm_issues = json.loads(json_match.group())
                for issue in llm_issues[:10]:  # Limit to 10 issues
                    issues.append(ConsistencyIssue(
                        type="continuity",
                        severity=issue.get("severity", "warning"),
                        description=issue.get("issue", "Continuity issue detected"),
                        location=issue.get("location"),
                        suggestion="Review and verify this section"
                    ))
        except json.JSONDecodeError:
            pass
            
    except Exception as e:
        logger.warning(f"LLM continuity check failed: {e}")
    
    return issues


@router.post("/check-chapter/{chapter_id}", response_model=ConsistencyReport)
async def check_chapter_consistency(
    chapter_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Check a specific chapter for consistency issues."""
    
    # Get chapter content
    result = await db.execute(
        text("""
            SELECT c.content, c.title, b.series_id
            FROM chapters c
            LEFT JOIN books b ON c.book_id = b.id
            WHERE c.id = :id
        """),
        {"id": chapter_id}
    )
    chapter = result.fetchone()
    
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    
    # Run consistency check
    request = ConsistencyCheck(
        content=chapter.content or "",
        series_id=chapter.series_id,
        language="zh-TW"
    )
    
    return await check_consistency(request, db)


@router.get("/rules/{series_id}")
async def get_consistency_rules(
    series_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all established rules for a series that are used in consistency checking."""
    
    context = await _get_worldbuilding_context(db, series_id)
    
    return {
        "series_id": series_id,
        "character_count": len(context["characters"]),
        "world_rules_count": len(context["world_rules"]),
        "power_system_count": len(context["power_system"]),
        "characters": [c["name"] for c in context["characters"]],
        "world_rules": [r["name"] for r in context["world_rules"]],
        "message": "These elements will be checked for consistency"
    }
