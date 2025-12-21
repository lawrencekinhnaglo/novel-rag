"""
Document Story Extraction Service

Extracts story elements from uploaded documents (novels, discussions, notes):
- Series/Book structure
- Characters and their traits
- World rules and magic systems
- Foreshadowing elements
- Settings and locations
- Plot points and arcs

All extracted items are created with verification_status='pending'
for user review in the Verification Hub.
"""

from typing import Dict, Any, List, Optional
from app.services.llm_service import get_llm_service
from app.services.embeddings import generate_embedding
from app.database.postgres import AsyncSessionLocal
from sqlalchemy import text
import json
import logging
import re
import asyncio

logger = logging.getLogger(__name__)


class DocumentExtractionService:
    """Extract story elements from uploaded documents."""
    
    def __init__(self, provider: str = None):
        self.llm = get_llm_service(provider)
    
    async def extract_from_document(
        self,
        content: str,
        filename: str,
        series_id: Optional[int] = None,
        book_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract all story elements from a document.
        All items created with verification_status='pending'.
        
        Args:
            content: Full text content of the document
            filename: Original filename for context
            series_id: Optional existing series to link to
            book_id: Optional existing book to link to
        
        Returns:
            Dict with extraction results and created item IDs
        """
        results = {
            "series": None,
            "books": [],
            "characters": [],
            "world_rules": [],
            "foreshadowing": [],
            "locations": [],
            "facts": [],
            "errors": []
        }
        
        # First, detect what kind of document this is
        doc_analysis = await self._analyze_document_type(content, filename)
        results["document_type"] = doc_analysis
        
        # Get or create series if needed
        if not series_id and doc_analysis.get("is_novel_related"):
            series_id = await self._extract_or_find_series(content, doc_analysis)
            if series_id:
                results["series"] = series_id
        elif series_id:
            results["series"] = series_id
        
        if not series_id:
            # Create a default series from the document
            series_id = await self._create_series_from_document(content, filename)
            results["series"] = series_id
        
        # Run extractions in parallel for efficiency
        extraction_tasks = [
            self._extract_characters(content, series_id, book_id),
            self._extract_world_rules(content, series_id, book_id),
            self._extract_foreshadowing(content, series_id, book_id),
            self._extract_locations(content, series_id),
            self._extract_story_facts(content, series_id, book_id)
        ]
        
        try:
            chars, rules, foreshadowing, locations, facts = await asyncio.gather(
                *extraction_tasks, return_exceptions=True
            )
            
            results["characters"] = chars if not isinstance(chars, Exception) else []
            results["world_rules"] = rules if not isinstance(rules, Exception) else []
            results["foreshadowing"] = foreshadowing if not isinstance(foreshadowing, Exception) else []
            results["locations"] = locations if not isinstance(locations, Exception) else []
            results["facts"] = facts if not isinstance(facts, Exception) else []
            
            # Log any errors
            for name, result in [("characters", chars), ("world_rules", rules), 
                                  ("foreshadowing", foreshadowing), ("locations", locations),
                                  ("facts", facts)]:
                if isinstance(result, Exception):
                    results["errors"].append(f"{name}: {str(result)}")
                    logger.error(f"Extraction error for {name}: {result}")
        
        except Exception as e:
            logger.error(f"Document extraction failed: {e}")
            results["errors"].append(str(e))
        
        # Calculate totals
        results["total_extracted"] = (
            len(results.get("characters", [])) +
            len(results.get("world_rules", [])) +
            len(results.get("foreshadowing", [])) +
            len(results.get("locations", [])) +
            len(results.get("facts", []))
        )
        
        return results
    
    async def _analyze_document_type(self, content: str, filename: str) -> Dict[str, Any]:
        """Analyze what type of document this is."""
        sample = content[:3000]
        
        prompt = f"""Analyze this document and determine what type of content it contains.

FILENAME: {filename}

CONTENT SAMPLE:
{sample}

Determine:
1. Is this novel/story content or discussion about a novel?
2. Does it contain chapter content, character descriptions, world-building, or plot notes?
3. What elements can be extracted?

Respond in JSON:
{{
    "is_novel_related": true/false,
    "content_types": ["chapter", "character_notes", "world_building", "plot_notes", "discussion"],
    "detected_series_title": "series name if mentioned or null",
    "detected_book_title": "book name if mentioned or null",
    "language": "en|zh-TW|zh-CN",
    "extraction_potential": {{
        "characters": "high|medium|low|none",
        "world_rules": "high|medium|low|none",
        "foreshadowing": "high|medium|low|none",
        "locations": "high|medium|low|none"
    }},
    "summary": "brief description of the document"
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            return self._extract_json(response)
        except:
            return {"is_novel_related": True, "content_types": ["unknown"], "language": "en"}
    
    async def _extract_or_find_series(self, content: str, doc_analysis: Dict) -> Optional[int]:
        """Find existing series or prepare for new one."""
        detected_title = doc_analysis.get("detected_series_title")
        
        if detected_title:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    text("SELECT id FROM series WHERE title ILIKE :title LIMIT 1"),
                    {"title": f"%{detected_title}%"}
                )
                row = result.fetchone()
                if row:
                    return row.id
        
        return None
    
    async def _create_series_from_document(self, content: str, filename: str) -> int:
        """Create a new series from document content."""
        prompt = f"""Based on this document, extract series information.

DOCUMENT (sample):
{content[:2500]}

Extract:
- Title: The name of the series/story
- Premise: What the story is about
- Themes: Main themes

JSON response:
{{
    "title": "Series Title",
    "premise": "What the story is about",
    "themes": ["theme1", "theme2"],
    "planned_books": 1
}}

If you can't determine a title, use the filename: {filename}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        try:
            data = self._extract_json(response)
        except:
            data = {"title": filename.rsplit('.', 1)[0], "premise": "", "themes": [], "planned_books": 1}
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("""
                    INSERT INTO series (title, premise, themes, total_planned_books, verification_status, metadata)
                    VALUES (:title, :premise, :themes, :total_planned_books, 'pending', :metadata)
                    RETURNING id
                """),
                {
                    "title": data.get("title", filename),
                    "premise": data.get("premise", ""),
                    "themes": data.get("themes", []),
                    "total_planned_books": data.get("planned_books", 1),
                    "metadata": json.dumps({"auto_extracted": True, "source_file": filename})
                }
            )
            await db.commit()
            row = result.fetchone()
            return row.id
    
    async def _extract_characters(
        self,
        content: str,
        series_id: int,
        book_id: Optional[int]
    ) -> List[Dict]:
        """Extract characters from document."""
        
        # Get existing characters to avoid duplicates
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                text("SELECT name FROM character_profiles WHERE series_id = :sid"),
                {"sid": series_id}
            )
            existing_names = [r.name.lower() for r in existing.fetchall()]
        
        # Process in chunks if document is large
        chunks = self._chunk_for_extraction(content, 4000)
        all_characters = []
        
        for chunk in chunks[:3]:  # Process first 3 chunks
            prompt = f"""Extract CHARACTER information from this text.

EXISTING CHARACTERS (don't duplicate): {', '.join(existing_names) if existing_names else 'None yet'}

TEXT:
{chunk}

For each NEW character mentioned with enough detail, extract:
- name: Character's name
- aliases: Other names they go by
- description: Who they are
- personality: Their personality traits
- appearance: Physical description if mentioned
- background: Their history/backstory
- goals: What they want
- speech_patterns: How they talk

Only include characters with meaningful presence, not background mentions.

JSON response:
{{"characters": [
  {{
    "name": "Character Name",
    "aliases": ["nickname"],
    "description": "who they are",
    "personality": "traits",
    "appearance": "physical details or null",
    "background": "history or null",
    "goals": "what they want or null",
    "speech_patterns": "how they talk or null",
    "confidence": 0.0-1.0
  }}
]}}
"""
            
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            try:
                data = self._extract_json(response)
                for char in data.get("characters", []):
                    if char.get("name") and char.get("name", "").lower() not in existing_names:
                        all_characters.append(char)
                        existing_names.append(char["name"].lower())
            except Exception as e:
                logger.warning(f"Character extraction chunk failed: {e}")
        
        # Save characters to database
        created = []
        async with AsyncSessionLocal() as db:
            for char in all_characters:
                try:
                    embedding = generate_embedding(
                        f"{char.get('name', '')} {char.get('description', '')} {char.get('personality', '')}"
                    )
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO character_profiles 
                            (series_id, name, aliases, description, personality, appearance, 
                             background, goals, speech_patterns,
                             verification_status, auto_extracted, extraction_source, embedding)
                            VALUES (:series_id, :name, :aliases, :description, :personality, :appearance,
                                    :background, :goals, :speech,
                                    'pending', TRUE, :source, :embedding)
                            ON CONFLICT (series_id, name) DO NOTHING
                            RETURNING id, name
                        """),
                        {
                            "series_id": series_id,
                            "name": char.get("name", "Unknown"),
                            "aliases": char.get("aliases", []),
                            "description": char.get("description"),
                            "personality": char.get("personality"),
                            "appearance": char.get("appearance"),
                            "background": char.get("background"),
                            "goals": char.get("goals"),
                            "speech": char.get("speech_patterns"),
                            "source": f"Auto-extracted from uploaded document",
                            "embedding": str(embedding)
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": row.name,
                            "confidence": char.get("confidence", 0.7)
                        })
                except Exception as e:
                    logger.warning(f"Failed to save character {char.get('name')}: {e}")
            
            await db.commit()
        
        return created
    
    async def _extract_world_rules(
        self,
        content: str,
        series_id: int,
        book_id: Optional[int]
    ) -> List[Dict]:
        """Extract world-building rules from document."""
        
        chunks = self._chunk_for_extraction(content, 4000)
        all_rules = []
        
        for chunk in chunks[:3]:
            prompt = f"""Extract WORLD-BUILDING RULES from this text.

Look for:
- Magic system rules/limitations
- Technology constraints  
- Social/political rules and customs
- Geography/travel rules
- Species/creature rules
- Historical facts about the world

TEXT:
{chunk}

Only extract DEFINITIVE rules that are clearly stated or demonstrated.

JSON response:
{{"rules": [
  {{
    "category": "magic|technology|society|geography|biology|history|other",
    "name": "Short rule name",
    "description": "Full rule description",
    "exceptions": ["exception1", "exception2"],
    "is_hard_rule": true if absolute / false if can be bent,
    "source_text": "Quote that establishes this rule",
    "confidence": 0.0-1.0
  }}
]}}

If nothing found: {{"rules": []}}
"""
            
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            try:
                data = self._extract_json(response)
                all_rules.extend(data.get("rules", []))
            except Exception as e:
                logger.warning(f"World rule extraction chunk failed: {e}")
        
        # Save to database
        created = []
        async with AsyncSessionLocal() as db:
            for rule in all_rules:
                if not rule.get("name") or not rule.get("description"):
                    continue
                
                try:
                    result = await db.execute(
                        text("""
                            INSERT INTO world_rules 
                            (series_id, rule_category, rule_name, rule_description, 
                             exceptions, is_hard_rule, source_text,
                             verification_status, auto_extracted, extraction_confidence)
                            VALUES (:series_id, :category, :name, :description,
                                    :exceptions, :is_hard, :source_text,
                                    'pending', TRUE, :confidence)
                            RETURNING id, rule_name
                        """),
                        {
                            "series_id": series_id,
                            "category": rule.get("category", "other"),
                            "name": rule.get("name"),
                            "description": rule.get("description"),
                            "exceptions": rule.get("exceptions", []),
                            "is_hard": rule.get("is_hard_rule", True),
                            "source_text": rule.get("source_text"),
                            "confidence": rule.get("confidence", 0.7)
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": row.rule_name,
                            "confidence": rule.get("confidence", 0.7)
                        })
                except Exception as e:
                    logger.warning(f"Failed to save world rule: {e}")
            
            await db.commit()
        
        return created
    
    async def _extract_foreshadowing(
        self,
        content: str,
        series_id: int,
        book_id: Optional[int]
    ) -> List[Dict]:
        """Extract foreshadowing elements from document."""
        
        chunks = self._chunk_for_extraction(content, 4000)
        all_seeds = []
        
        for chunk in chunks[:3]:
            prompt = f"""Analyze this text for FORESHADOWING elements.

Look for:
- Mysterious hints about future events
- Chekhov's guns (objects/details that seem important)
- Prophecies or predictions
- Symbolic imagery that might pay off later
- Subtle character setup for future arcs

TEXT:
{chunk}

JSON response:
{{"seeds": [
  {{
    "title": "Short descriptive title",
    "planted_text": "The exact quote that plants the seed",
    "seed_type": "plot|character|thematic|chekhov_gun|prophecy",
    "intended_payoff": "What this might be leading to",
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
            
            try:
                data = self._extract_json(response)
                all_seeds.extend(data.get("seeds", []))
            except Exception as e:
                logger.warning(f"Foreshadowing extraction chunk failed: {e}")
        
        # Save to database
        created = []
        async with AsyncSessionLocal() as db:
            for seed in all_seeds:
                if not seed.get("title") or not seed.get("planted_text"):
                    continue
                
                try:
                    result = await db.execute(
                        text("""
                            INSERT INTO foreshadowing 
                            (series_id, title, planted_book, planted_chapter, planted_text,
                             seed_type, subtlety, intended_payoff, status,
                             verification_status, auto_extracted, extraction_confidence)
                            VALUES (:series_id, :title, :book, 1, :text,
                                    :seed_type, :subtlety, :payoff, 'planted',
                                    'pending', TRUE, :confidence)
                            RETURNING id, title
                        """),
                        {
                            "series_id": series_id,
                            "title": seed.get("title"),
                            "book": book_id or 1,
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
                            "confidence": seed.get("confidence", 0.6)
                        })
                except Exception as e:
                    logger.warning(f"Failed to save foreshadowing: {e}")
            
            await db.commit()
        
        return created
    
    async def _extract_locations(
        self,
        content: str,
        series_id: int
    ) -> List[Dict]:
        """Extract locations/settings from document."""
        
        prompt = f"""Extract LOCATIONS and SETTINGS from this text.

TEXT (sample):
{content[:4000]}

Look for:
- Named places (cities, kingdoms, buildings)
- Important settings where events happen
- Geographical features

JSON response:
{{"locations": [
  {{
    "name": "Location Name",
    "type": "city|kingdom|building|region|landmark|other",
    "description": "What this place is like",
    "significance": "Why it matters to the story",
    "confidence": 0.0-1.0
  }}
]}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        # Note: We'd save these to a locations table if we had one
        # For now, save as story_facts
        created = []
        try:
            data = self._extract_json(response)
            locations = data.get("locations", [])
            
            async with AsyncSessionLocal() as db:
                for loc in locations:
                    if not loc.get("name"):
                        continue
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO story_facts 
                            (series_id, fact_description, fact_category, importance, 
                             verification_status, auto_extracted)
                            VALUES (:series_id, :description, 'location', 'normal',
                                    'pending', TRUE)
                            RETURNING id
                        """),
                        {
                            "series_id": series_id,
                            "description": f"Location: {loc.get('name')} - {loc.get('description', '')} ({loc.get('type', 'place')})"
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": loc.get("name"),
                            "type": "location",
                            "confidence": loc.get("confidence", 0.7)
                        })
                
                await db.commit()
        
        except Exception as e:
            logger.warning(f"Location extraction failed: {e}")
        
        return created
    
    async def _extract_story_facts(
        self,
        content: str,
        series_id: int,
        book_id: Optional[int]
    ) -> List[Dict]:
        """Extract key story facts from document."""
        
        prompt = f"""Extract KEY STORY FACTS from this text.

TEXT (sample):
{content[:4000]}

Look for:
- Important plot points
- Revealed secrets
- Historical events in the story
- Relationships between characters
- Major decisions or turning points

JSON response:
{{"facts": [
  {{
    "description": "The fact description",
    "category": "plot|character|world|secret|relationship",
    "is_secret": true if hidden from characters / false if known,
    "importance": "trivial|normal|major|critical",
    "confidence": 0.0-1.0
  }}
]}}

Only include NOTABLE facts, not every detail.
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        created = []
        try:
            data = self._extract_json(response)
            facts = data.get("facts", [])
            
            async with AsyncSessionLocal() as db:
                for fact in facts:
                    if not fact.get("description"):
                        continue
                    
                    # Only save major/critical facts
                    if fact.get("importance") not in ["major", "critical"]:
                        continue
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO story_facts 
                            (series_id, fact_description, fact_category, is_secret, importance,
                             verification_status, auto_extracted)
                            VALUES (:series_id, :description, :category, :is_secret, :importance,
                                    'pending', TRUE)
                            RETURNING id
                        """),
                        {
                            "series_id": series_id,
                            "description": fact.get("description")[:500],
                            "category": fact.get("category", "plot"),
                            "is_secret": fact.get("is_secret", False),
                            "importance": fact.get("importance", "normal")
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "description": fact.get("description")[:100],
                            "confidence": fact.get("confidence", 0.7)
                        })
                
                await db.commit()
        
        except Exception as e:
            logger.warning(f"Story facts extraction failed: {e}")
        
        return created
    
    def _chunk_for_extraction(self, content: str, chunk_size: int = 4000) -> List[str]:
        """Split content into chunks for processing."""
        chunks = []
        words = content.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1
            
            if current_size >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No JSON found in response")


def get_document_extraction_service(provider: str = None) -> DocumentExtractionService:
    """Get document extraction service instance."""
    return DocumentExtractionService(provider)

