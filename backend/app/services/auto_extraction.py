"""
Auto-Extraction Service

Automatically extracts story elements from chapter content:
- Characters (new or updates)
- World Rules (magic system, society rules, etc.)
- Foreshadowing Seeds
- Potential Seed Payoffs

All extracted items are created with verification_status='pending'
and will NOT be used in RAG until approved in the Verification Hub.
"""

from typing import Dict, Any, List, Optional
from app.services.llm_service import get_llm_service
from app.services.embeddings import generate_embedding
from app.database.postgres import AsyncSessionLocal
from sqlalchemy import text
import json
import logging
import re

logger = logging.getLogger(__name__)


class AutoExtractionService:
    """Extract story elements automatically and create pending records."""
    
    def __init__(self, provider: str = None):
        self.llm = get_llm_service(provider)
    
    async def extract_all_from_chapter(
        self,
        chapter_content: str,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> Dict[str, Any]:
        """
        Extract all story elements from a chapter.
        All items created with verification_status='pending'.
        """
        results = {
            "characters": [],
            "world_rules": [],
            "foreshadowing": [],
            "payoffs": [],
            "errors": []
        }
        
        # Run extraction
        try:
            # Extract characters
            chars = await self._extract_characters(
                chapter_content, series_id, book_id, chapter_number
            )
            results["characters"] = chars
        except Exception as e:
            results["errors"].append(f"Character extraction: {e}")
            logger.error(f"Character extraction failed: {e}")
        
        try:
            # Extract world rules
            rules = await self._extract_world_rules(
                chapter_content, series_id, book_id, chapter_number
            )
            results["world_rules"] = rules
        except Exception as e:
            results["errors"].append(f"World rule extraction: {e}")
            logger.error(f"World rule extraction failed: {e}")
        
        try:
            # Extract foreshadowing
            seeds = await self._extract_foreshadowing(
                chapter_content, series_id, book_id, chapter_number
            )
            results["foreshadowing"] = seeds
        except Exception as e:
            results["errors"].append(f"Foreshadowing extraction: {e}")
            logger.error(f"Foreshadowing extraction failed: {e}")
        
        try:
            # Check for seed payoffs
            payoffs = await self._detect_payoffs(
                chapter_content, series_id, book_id, chapter_number
            )
            results["payoffs"] = payoffs
        except Exception as e:
            results["errors"].append(f"Payoff detection: {e}")
            logger.error(f"Payoff detection failed: {e}")
        
        return results
    
    async def _extract_characters(
        self,
        content: str,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> List[Dict]:
        """Extract character information from chapter."""
        
        # Get existing characters to avoid duplicates
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                text("SELECT name FROM character_profiles WHERE series_id = :sid"),
                {"sid": series_id}
            )
            existing_names = [r.name.lower() for r in existing.fetchall()]
        
        prompt = f"""Extract CHARACTER information from this chapter.

EXISTING CHARACTERS (don't duplicate): {', '.join(existing_names) if existing_names else 'None yet'}

CHAPTER CONTENT:
{content[:4000]}

For EACH NEW character or significant character detail, extract:
- name: Character name
- description: Brief description
- personality: Personality traits shown
- appearance: Physical description if mentioned
- speech_patterns: How they talk (dialect, vocabulary)
- is_new: true if not in existing list

Only include characters with meaningful presence, not background mentions.

JSON response:
{{"characters": [
  {{
    "name": "Character Name",
    "description": "who they are",
    "personality": "traits shown in this chapter",
    "appearance": "physical details or null",
    "speech_patterns": "how they talk or null",
    "is_new": true,
    "confidence": 0.0-1.0
  }}
]}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        created = []
        try:
            data = self._extract_json(response)
            characters = data.get("characters", [])
            
            async with AsyncSessionLocal() as db:
                for char in characters:
                    if not char.get("name"):
                        continue
                    
                    # Check if already exists
                    if char.get("name", "").lower() in existing_names:
                        # TODO: Could update existing character with new info
                        continue
                    
                    # Create with pending status
                    embedding = generate_embedding(
                        f"{char.get('name', '')} {char.get('description', '')} {char.get('personality', '')}"
                    )
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO character_profiles 
                            (series_id, name, description, personality, appearance, speech_patterns,
                             first_appearance_book, first_appearance_chapter,
                             verification_status, auto_extracted, extraction_source, embedding)
                            VALUES (:series_id, :name, :description, :personality, :appearance, :speech,
                                    :book, :chapter, 'pending', TRUE, :source, :embedding)
                            ON CONFLICT (series_id, name) DO NOTHING
                            RETURNING id, name
                        """),
                        {
                            "series_id": series_id,
                            "name": char.get("name", "Unknown"),
                            "description": char.get("description"),
                            "personality": char.get("personality"),
                            "appearance": char.get("appearance"),
                            "speech": char.get("speech_patterns"),
                            "book": book_id,
                            "chapter": chapter_number,
                            "source": f"Auto-extracted from Book {book_id}, Chapter {chapter_number}",
                            "embedding": str(embedding)
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": row.name,
                            "type": "character",
                            "confidence": char.get("confidence", 0.8)
                        })
                
                await db.commit()
        
        except Exception as e:
            logger.error(f"Failed to save extracted characters: {e}")
        
        return created
    
    async def _extract_world_rules(
        self,
        content: str,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> List[Dict]:
        """Extract world-building rules from chapter."""
        
        prompt = f"""Extract WORLD RULES from this chapter - rules about how the world works.

Look for:
- Magic system rules/limitations
- Technology constraints
- Social/political rules
- Geography/travel rules
- Species/creature rules

CHAPTER CONTENT:
{content[:4000]}

Only extract DEFINITIVE rules that are clearly established, not just hints.

JSON response:
{{"rules": [
  {{
    "category": "magic|technology|society|geography|biology|other",
    "name": "Short rule name",
    "description": "Full rule description",
    "source_text": "Quote from chapter that establishes this",
    "is_hard_rule": true if absolute rule / false if can be bent,
    "confidence": 0.0-1.0
  }}
]}}

If no clear rules found: {{"rules": []}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        created = []
        try:
            data = self._extract_json(response)
            rules = data.get("rules", [])
            
            async with AsyncSessionLocal() as db:
                for rule in rules:
                    if not rule.get("name") or not rule.get("description"):
                        continue
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO world_rules 
                            (series_id, rule_category, rule_name, rule_description, 
                             source_book, source_chapter, source_text, is_hard_rule,
                             verification_status, auto_extracted, extraction_confidence)
                            VALUES (:series_id, :category, :name, :description,
                                    :book, :chapter, :source_text, :is_hard,
                                    'pending', TRUE, :confidence)
                            RETURNING id, rule_name
                        """),
                        {
                            "series_id": series_id,
                            "category": rule.get("category", "other"),
                            "name": rule.get("name"),
                            "description": rule.get("description"),
                            "book": book_id,
                            "chapter": chapter_number,
                            "source_text": rule.get("source_text"),
                            "is_hard": rule.get("is_hard_rule", True),
                            "confidence": rule.get("confidence", 0.7)
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": row.rule_name,
                            "type": "world_rule",
                            "confidence": rule.get("confidence", 0.7)
                        })
                
                await db.commit()
        
        except Exception as e:
            logger.error(f"Failed to save extracted world rules: {e}")
        
        return created
    
    async def _extract_foreshadowing(
        self,
        content: str,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> List[Dict]:
        """Extract potential foreshadowing from chapter."""
        
        prompt = f"""Analyze this chapter for FORESHADOWING elements.

Look for:
- Mysterious hints about the future
- Chekhov's guns (objects/details that seem important)
- Prophecies or predictions
- Symbolic imagery
- Subtle character setup for future arcs

CHAPTER CONTENT:
{content[:4000]}

For each potential foreshadowing element:

JSON response:
{{"seeds": [
  {{
    "title": "Short descriptive title",
    "planted_text": "The exact quote that plants the seed",
    "seed_type": "plot|character|thematic|chekhov_gun|prophecy",
    "intended_payoff": "What this might be leading to (your analysis)",
    "subtlety": 1-5 (1=obvious, 5=very subtle),
    "confidence": 0.0-1.0
  }}
]}}

If nothing found: {{"seeds": []}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        created = []
        try:
            data = self._extract_json(response)
            seeds = data.get("seeds", [])
            
            async with AsyncSessionLocal() as db:
                for seed in seeds:
                    if not seed.get("title") or not seed.get("planted_text"):
                        continue
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO foreshadowing 
                            (series_id, title, planted_book, planted_chapter, planted_text,
                             seed_type, subtlety, intended_payoff, status,
                             verification_status, auto_extracted, extraction_confidence)
                            VALUES (:series_id, :title, :book, :chapter, :text,
                                    :seed_type, :subtlety, :payoff, 'planted',
                                    'pending', TRUE, :confidence)
                            RETURNING id, title
                        """),
                        {
                            "series_id": series_id,
                            "title": seed.get("title"),
                            "book": book_id,
                            "chapter": chapter_number,
                            "text": seed.get("planted_text"),
                            "seed_type": seed.get("seed_type", "plot"),
                            "subtlety": min(5, max(1, seed.get("subtlety", 3))),
                            "payoff": seed.get("intended_payoff"),
                            "confidence": seed.get("confidence", 0.6)
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": row.title,
                            "type": "foreshadowing",
                            "confidence": seed.get("confidence", 0.6)
                        })
                
                await db.commit()
        
        except Exception as e:
            logger.error(f"Failed to save extracted foreshadowing: {e}")
        
        return created
    
    async def _detect_payoffs(
        self,
        content: str,
        series_id: int,
        book_id: int,
        chapter_number: int
    ) -> List[Dict]:
        """Detect if any planted seeds are paid off in this chapter."""
        
        # Get existing planted seeds
        async with AsyncSessionLocal() as db:
            seeds_result = await db.execute(
                text("""
                    SELECT id, title, planted_text, intended_payoff
                    FROM foreshadowing
                    WHERE series_id = :sid 
                    AND status IN ('planted', 'reinforced')
                    AND verification_status = 'approved'
                """),
                {"sid": series_id}
            )
            seeds = seeds_result.fetchall()
        
        if not seeds:
            return []
        
        seeds_text = "\n".join([
            f"- ID:{s.id} | {s.title}: {s.planted_text[:100]}... (payoff: {s.intended_payoff or 'unknown'})"
            for s in seeds
        ])
        
        prompt = f"""Check if any of these PLANTED FORESHADOWING SEEDS are PAID OFF in this chapter.

PLANTED SEEDS TO CHECK:
{seeds_text}

CHAPTER CONTENT:
{content[:4000]}

A payoff is when a previously planted hint is resolved or revealed.

JSON response:
{{"payoffs": [
  {{
    "seed_id": 123,
    "seed_title": "The seed title",
    "payoff_text": "Quote from chapter that pays it off",
    "confidence": 0.0-1.0
  }}
]}}

If no payoffs detected: {{"payoffs": []}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        detected = []
        try:
            data = self._extract_json(response)
            payoffs = data.get("payoffs", [])
            
            async with AsyncSessionLocal() as db:
                for payoff in payoffs:
                    if not payoff.get("seed_id"):
                        continue
                    
                    # Create a pending payoff record (doesn't update the seed yet)
                    # User needs to approve in verification hub
                    result = await db.execute(
                        text("""
                            INSERT INTO story_analyses
                            (series_id, book_id, chapter_id, analysis_type, query,
                             analysis_result, severity, metadata)
                            VALUES (:series_id, :book_id, NULL, 'pending_payoff', :query,
                                    :result, 'info', :metadata)
                            RETURNING id
                        """),
                        {
                            "series_id": series_id,
                            "book_id": book_id,
                            "query": f"Potential payoff for seed: {payoff.get('seed_title')}",
                            "result": payoff.get("payoff_text", ""),
                            "metadata": json.dumps({
                                "seed_id": payoff.get("seed_id"),
                                "payoff_chapter": chapter_number,
                                "confidence": payoff.get("confidence", 0.7),
                                "requires_verification": True
                            })
                        }
                    )
                    row = result.fetchone()
                    if row:
                        detected.append({
                            "id": row.id,
                            "seed_id": payoff.get("seed_id"),
                            "name": payoff.get("seed_title"),
                            "type": "payoff",
                            "confidence": payoff.get("confidence", 0.7)
                        })
                
                await db.commit()
        
        except Exception as e:
            logger.error(f"Failed to detect payoffs: {e}")
        
        return detected
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No JSON found")


def get_auto_extraction_service(provider: str = None) -> AutoExtractionService:
    """Get auto-extraction service instance."""
    return AutoExtractionService(provider)

