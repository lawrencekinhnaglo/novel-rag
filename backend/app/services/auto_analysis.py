"""
Automatic Background Analysis Service

Runs LLM analysis automatically when content is saved:
1. Consistency checking on chapter save
2. Foreshadowing opportunity detection
3. Character voice validation
4. Auto-extract facts from chapters
5. Auto-extract characters, world rules, and foreshadowing seeds

All auto-extracted items are created with verification_status='pending'
and must be approved in the Verification Hub before being used in RAG.
"""

from typing import Optional, Dict, Any, List
from app.services.llm_service import get_llm_service
from app.services.embeddings import generate_embedding
from app.database.postgres import AsyncSessionLocal
from sqlalchemy import text
import json
import logging
import asyncio

logger = logging.getLogger(__name__)


class AutoAnalysisService:
    """Background analysis that runs automatically."""
    
    def __init__(self, provider: str = None):
        self.llm = get_llm_service(provider)
    
    async def on_chapter_save(
        self,
        chapter_id: int,
        chapter_content: str,
        book_id: int,
        series_id: int,
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        Triggered automatically when a chapter is saved.
        Runs multiple analyses in parallel.
        All extracted items are created with verification_status='pending'.
        """
        results = {}
        
        # Run analyses in parallel
        tasks = [
            self._auto_consistency_check(chapter_content, series_id),
            self._auto_detect_foreshadowing(chapter_content, series_id, chapter_number),
            self._auto_extract_facts(chapter_content, series_id, chapter_number),
            self._auto_generate_summary(chapter_content, chapter_id),
            self._auto_extract_story_elements(chapter_content, series_id, book_id, chapter_number)
        ]
        
        try:
            consistency, foreshadowing, facts, summary, extractions = await asyncio.gather(
                *tasks, return_exceptions=True
            )
            
            results['consistency'] = consistency if not isinstance(consistency, Exception) else {"error": str(consistency)}
            results['foreshadowing'] = foreshadowing if not isinstance(foreshadowing, Exception) else {"error": str(foreshadowing)}
            results['extracted_facts'] = facts if not isinstance(facts, Exception) else {"error": str(facts)}
            results['summary'] = summary if not isinstance(summary, Exception) else {"error": str(summary)}
            results['auto_extractions'] = extractions if not isinstance(extractions, Exception) else {"error": str(extractions)}
            
        except Exception as e:
            logger.error(f"Auto-analysis failed: {e}")
            results['error'] = str(e)
        
        return results
    
    async def _auto_extract_story_elements(
        self,
        content: str,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        Auto-extract characters, world rules, foreshadowing, and payoffs.
        All created with verification_status='pending'.
        """
        try:
            from app.services.auto_extraction import get_auto_extraction_service
            extraction_service = get_auto_extraction_service()
            return await extraction_service.extract_all_from_chapter(
                chapter_content=content,
                series_id=series_id,
                book_id=book_id,
                chapter_number=chapter_number
            )
        except Exception as e:
            logger.error(f"Auto-extraction failed: {e}")
            return {"error": str(e)}
    
    async def _auto_consistency_check(
        self,
        content: str,
        series_id: int
    ) -> Dict[str, Any]:
        """Quick consistency check against established rules."""
        async with AsyncSessionLocal() as db:
            # Get world rules (only approved ones for consistency checking)
            rules_result = await db.execute(
                text("""
                    SELECT rule_name, rule_description, is_hard_rule
                    FROM world_rules
                    WHERE series_id = :series_id 
                    AND (verification_status = 'approved' OR verification_status IS NULL)
                    LIMIT 20
                """),
                {"series_id": series_id}
            )
            rules = rules_result.fetchall()
            
            if not rules:
                return {"status": "skipped", "reason": "No world rules defined"}
        
        rules_text = "\n".join([
            f"- {'[HARD]' if r.is_hard_rule else '[SOFT]'} {r.rule_name}: {r.rule_description}"
            for r in rules
        ])
        
        prompt = f"""Quick consistency check. List ONLY clear violations, nothing else.

RULES:
{rules_text}

CONTENT (excerpt):
{content[:2000]}

Respond ONLY in JSON:
{{"violations": [{{"rule": "rule name", "issue": "what's wrong", "severity": "minor|major|critical"}}], "clean": true/false}}

If no violations, respond: {{"violations": [], "clean": true}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        try:
            return self._extract_json(response)
        except:
            return {"raw": response[:500]}
    
    async def _auto_detect_foreshadowing(
        self,
        content: str,
        series_id: int,
        chapter_number: int
    ) -> Dict[str, Any]:
        """Detect potential foreshadowing in the content."""
        async with AsyncSessionLocal() as db:
            # Get existing seeds to check for reinforcement opportunities (only approved ones)
            seeds_result = await db.execute(
                text("""
                    SELECT title, intended_payoff
                    FROM foreshadowing
                    WHERE series_id = :series_id 
                    AND status IN ('planted', 'reinforced')
                    AND (verification_status = 'approved' OR verification_status IS NULL)
                    LIMIT 10
                """),
                {"series_id": series_id}
            )
            seeds = seeds_result.fetchall()
        
        seeds_text = "\n".join([f"- {s.title}: {s.intended_payoff}" for s in seeds]) if seeds else "None yet"
        
        prompt = f"""Analyze for foreshadowing elements. Be brief.

EXISTING SEEDS TO WATCH FOR:
{seeds_text}

CHAPTER {chapter_number} CONTENT:
{content[:2000]}

Find:
1. New foreshadowing elements (hints at future events)
2. Reinforcement of existing seeds
3. Potential Chekhov's guns (objects/details that should pay off)

JSON response:
{{"new_seeds": [{{"text": "quoted text", "foreshadows": "what it hints at"}}], "reinforcements": [{{"seed": "which seed", "text": "reinforcing text"}}], "chekhovs_guns": ["item/detail that needs payoff"]}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        try:
            return self._extract_json(response)
        except:
            return {"raw": response[:500]}
    
    async def _auto_extract_facts(
        self,
        content: str,
        series_id: int,
        chapter_number: int
    ) -> Dict[str, Any]:
        """Extract notable facts/events that characters learn."""
        prompt = f"""Extract key FACTS from this chapter that characters learn or that are revealed.

CHAPTER {chapter_number}:
{content[:2500]}

For each fact, note:
- What the fact is
- Which characters now know it
- Is it a secret (known only to some)?

JSON response:
{{"facts": [{{"description": "the fact", "characters_who_know": ["name1", "name2"], "is_secret": true/false, "importance": "trivial|normal|major|critical"}}]}}

Only include NOTABLE facts, not every detail.
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            result = self._extract_json(response)
            
            # Auto-save important facts to database
            if result.get("facts"):
                await self._save_extracted_facts(
                    facts=result["facts"],
                    series_id=series_id,
                    chapter_number=chapter_number
                )
            
            return result
        except:
            return {"raw": response[:500]}
    
    async def _save_extracted_facts(
        self,
        facts: List[Dict],
        series_id: int,
        chapter_number: int
    ):
        """Save extracted facts to the database with pending verification status."""
        async with AsyncSessionLocal() as db:
            for fact in facts:
                if fact.get("importance") in ["major", "critical"]:
                    try:
                        # Insert the fact with pending status for verification
                        result = await db.execute(
                            text("""
                                INSERT INTO story_facts 
                                (series_id, fact_description, fact_category, established_in_chapter, 
                                 is_secret, importance, verification_status, auto_extracted)
                                VALUES (:series_id, :description, 'auto_extracted', :chapter,
                                        :is_secret, :importance, 'pending', TRUE)
                                ON CONFLICT DO NOTHING
                                RETURNING id
                            """),
                            {
                                "series_id": series_id,
                                "description": fact.get("description", "")[:500],
                                "chapter": chapter_number,
                                "is_secret": fact.get("is_secret", False),
                                "importance": fact.get("importance", "normal")
                            }
                        )
                        fact_row = result.fetchone()
                        
                        if fact_row:
                            # Link characters who know this fact
                            for char_name in fact.get("characters_who_know", []):
                                await db.execute(
                                    text("""
                                        INSERT INTO character_knowledge (character_id, fact_id, learned_in_chapter, learned_how)
                                        SELECT cp.id, :fact_id, :chapter, 'auto_detected'
                                        FROM character_profiles cp
                                        WHERE cp.series_id = :series_id AND cp.name ILIKE :name
                                        ON CONFLICT DO NOTHING
                                    """),
                                    {
                                        "fact_id": fact_row.id,
                                        "chapter": chapter_number,
                                        "series_id": series_id,
                                        "name": f"%{char_name}%"
                                    }
                                )
                        
                    except Exception as e:
                        logger.warning(f"Failed to save fact: {e}")
            
            await db.commit()
    
    async def _auto_generate_summary(
        self,
        content: str,
        chapter_id: int
    ) -> Dict[str, Any]:
        """Generate a chapter summary."""
        prompt = f"""Write a 2-3 sentence summary of this chapter's key events.

{content[:3000]}

Be concise and focus on plot-relevant events only.
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        # Save summary to chapter
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE chapters SET summary = :summary WHERE id = :id"),
                {"summary": response[:500], "id": chapter_id}
            )
            await db.commit()
        
        return {"summary": response[:500]}
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No JSON found")


# Singleton for background tasks
_auto_service: Optional[AutoAnalysisService] = None

def get_auto_analysis_service(provider: str = None) -> AutoAnalysisService:
    global _auto_service
    if _auto_service is None:
        _auto_service = AutoAnalysisService(provider)
    return _auto_service


async def trigger_chapter_analysis(
    chapter_id: int,
    chapter_content: str,
    book_id: int,
    series_id: int,
    chapter_number: int
) -> Dict[str, Any]:
    """
    Call this after saving a chapter to trigger background analysis.
    Can be called as a background task.
    """
    service = get_auto_analysis_service()
    return await service.on_chapter_save(
        chapter_id=chapter_id,
        chapter_content=chapter_content,
        book_id=book_id,
        series_id=series_id,
        chapter_number=chapter_number
    )

