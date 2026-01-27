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
            "cultivation_system": None,
            "story_parts": [],
            "concepts": [],
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

        # Determine document type for specialized extraction
        is_setting_doc = self._is_setting_document(content, doc_analysis)
        is_cultivation_story = self._is_cultivation_story(content, doc_analysis)

        # For setting documents with messy content, run reconciliation first
        reconciliation = None
        if is_setting_doc:
            logger.info("Running content reconciliation for setting document...")
            reconciliation = await self._reconcile_content(content)
            results["reconciliation"] = reconciliation
            logger.info(f"Reconciliation complete: {len(reconciliation.get('character_mapping', {}))} character groups identified")

        # Build extraction tasks based on document type
        extraction_tasks = [
            self._extract_characters_with_reconciliation(content, series_id, book_id, is_setting_doc, reconciliation),
            self._extract_world_rules(content, series_id, book_id),
            self._extract_foreshadowing(content, series_id, book_id),
            self._extract_locations(content, series_id),
            self._extract_story_facts(content, series_id, book_id)
        ]

        # Add specialized extractions
        if is_cultivation_story:
            extraction_tasks.append(self._extract_cultivation_system(content, series_id))
        if is_setting_doc:
            extraction_tasks.append(self._extract_story_parts_with_reconciliation(content, series_id, reconciliation))
            extraction_tasks.append(self._extract_concepts(content, series_id))

        try:
            results_list = await asyncio.gather(*extraction_tasks, return_exceptions=True)

            # Map results
            result_names = ["characters", "world_rules", "foreshadowing", "locations", "facts"]
            if is_cultivation_story:
                result_names.append("cultivation_system")
            if is_setting_doc:
                result_names.extend(["story_parts", "concepts"])

            for i, name in enumerate(result_names):
                if i < len(results_list):
                    result = results_list[i]
                    if isinstance(result, Exception):
                        results["errors"].append(f"{name}: {str(result)}")
                        logger.error(f"Extraction error for {name}: {result}")
                    else:
                        results[name] = result

        except Exception as e:
            logger.error(f"Document extraction failed: {e}")
            results["errors"].append(str(e))

        # Calculate totals
        results["total_extracted"] = (
            len(results.get("characters", [])) +
            len(results.get("world_rules", [])) +
            len(results.get("foreshadowing", [])) +
            len(results.get("locations", [])) +
            len(results.get("facts", [])) +
            len(results.get("story_parts", [])) +
            len(results.get("concepts", []))
        )

        return results

    def _is_setting_document(self, content: str, analysis: Dict) -> bool:
        """Check if this is a story setting/worldbuilding document."""
        indicators = ["设定", "世界观", "体系", "第一部", "第二部", "角色", "主角", "反派", "境界", "天赋"]
        content_lower = content.lower()
        matches = sum(1 for ind in indicators if ind in content)
        return matches >= 3 or "设定" in content or "世界观" in content

    def _is_cultivation_story(self, content: str, analysis: Dict) -> bool:
        """Check if this is a cultivation/xianxia story."""
        indicators = ["修仙", "修炼", "境界", "金丹", "元婴", "化神", "渡劫", "飞升", "灵根", "灵气", "真仙", "天仙"]
        matches = sum(1 for ind in indicators if ind in content)
        return matches >= 2

    async def _reconcile_content(self, content: str) -> Dict[str, Any]:
        """
        Use LLM to reconcile messy/conflicting content in the document.

        This step:
        1. Identifies conflicting information (e.g., different part counts)
        2. Organizes characters by story parts
        3. Creates a canonical structure for extraction
        """
        # First pass: understand the document structure
        prompt = f"""Analyze this story setting document and reconcile any conflicting information.

DOCUMENT:
{content[:15000]}

This document may have:
- Conflicting information (e.g., mentions "第一部到第六部" but also mentions parts 7-10)
- Multiple versions of the same content
- Messy organization where characters appear in multiple sections

Your task:
1. Identify the TRUE structure of the story (how many parts/books)
2. Reconcile any timeline conflicts (e.g., "仙古(第七部)到荒古(第八部)" vs "第一部到第六部")
3. Map each character to their PRIMARY story part
4. Identify which content is "core canon" vs "draft ideas" vs "spinoff/外传"

IMPORTANT: The document mentions a timeline like "仙古(第七部)到荒古(第八部)再到上古(第九部)再到遠古(第十部)再到中古(第十一部)" - this means parts 1-6 are the "main story" and parts 7-11 might be prequels/background. Reconcile this.

JSON response:
{{
    "reconciliation": {{
        "total_main_parts": 6,
        "has_prequel_parts": true,
        "prequel_parts": [7, 8, 9, 10, 11],
        "timeline_order": "古代 -> 現代 explanation",
        "conflicts_found": [
            {{"issue": "description of conflict", "resolution": "how to resolve"}}
        ]
    }},
    "story_structure": {{
        "main_parts": [
            {{
                "part_number": 1,
                "title": "Part Title",
                "era": "時代名稱",
                "main_protagonists": ["name1", "name2"],
                "main_antagonists": ["name1"],
                "summary": "Brief summary"
            }}
        ],
        "prequel_parts": [
            {{
                "part_number": 7,
                "title": "仙古",
                "era": "仙古時代",
                "summary": "Background era"
            }}
        ],
        "spinoffs": [
            {{
                "title": "外传名稱",
                "main_character": "character name",
                "timeline": "when it takes place"
            }}
        ]
    }},
    "character_mapping": {{
        "part_1": ["袁复生", "君天命"],
        "part_2": ["墨千机", "况淳风", "林凡"],
        "part_3": ["凌绝", "叶留白"],
        "part_4": ["陆渊", "西门九歌"],
        "part_5": ["林玄策", "林镇狱"],
        "part_6": ["林敖雪", "李石堯"],
        "spinoff": ["许念/阿蛮", "叶留白"]
    }},
    "key_systems": {{
        "cultivation": "古典老派十五境 - description",
        "talents": ["天赋类型1", "天赋类型2"],
        "world_rules": ["牧羊纪元", "絕地天通"]
    }}
}}
"""

        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        try:
            return self._extract_json(response)
        except Exception as e:
            logger.warning(f"Content reconciliation failed: {e}")
            return {}

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
    
    async def _extract_characters_with_reconciliation(
        self,
        content: str,
        series_id: int,
        book_id: Optional[int],
        is_setting_doc: bool = False,
        reconciliation: Optional[Dict] = None
    ) -> List[Dict]:
        """Extract characters with reconciliation data for part mapping."""

        # Get character mapping from reconciliation if available
        char_mapping = reconciliation.get("character_mapping", {}) if reconciliation else {}

        # Get existing characters to avoid duplicates
        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                text("SELECT name FROM character_profiles WHERE series_id = :sid"),
                {"sid": series_id}
            )
            existing_names = [r.name.lower() for r in existing.fetchall()]

        # Process more chunks for setting documents (they have many characters)
        chunks = self._chunk_for_extraction(content, 5000)
        max_chunks = 10 if is_setting_doc else 3  # Increased for comprehensive extraction
        all_characters = []

        # Build part info string from reconciliation
        part_info = ""
        if char_mapping:
            part_info = "Character to Part Mapping (from reconciliation):\n"
            for part, chars in char_mapping.items():
                part_info += f"- {part}: {', '.join(chars)}\n"

        for chunk in chunks[:max_chunks]:
            # Use specialized prompt for setting documents
            if is_setting_doc:
                prompt = f"""Extract ALL CHARACTERS from this story setting document.

This is a story setting/worldbuilding document. Extract characters with their:
- Full profiles including abilities, talents, backgrounds
- Relationships to other characters
- Role in the story (protagonist, antagonist, supporting)
- Which story part they appear in (第一部, 第二部, etc.)

EXISTING CHARACTERS (don't duplicate): {', '.join(existing_names[:20]) if existing_names else 'None yet'}

TEXT:
{chunk}

For each character, extract:
- name: Character's primary name
- aliases: Other names, titles, nicknames (e.g., "长生道祖", "绝天魔主")
- role: protagonist|antagonist|supporting|minor
- generation: Which generation (第一代, 第二代, etc.) or story part they belong to
- faction: Which side/group they belong to
- description: Complete description including who they are
- abilities: Their powers, talents, special abilities (very important for cultivation stories)
- personality: Their personality traits
- background: Their history/backstory
- goals: What they want to achieve
- relationships: Key relationships with other characters

JSON response:
{{"characters": [
  {{
    "name": "Character Name",
    "aliases": ["alias1", "title1"],
    "role": "protagonist|antagonist|supporting|minor",
    "generation": "generation or story part",
    "faction": "faction name or null",
    "description": "complete description",
    "abilities": "powers and talents description",
    "personality": "personality traits",
    "background": "history and backstory",
    "goals": "what they want",
    "relationships": [{{"target": "Other Character", "type": "relationship type", "description": "details"}}],
    "confidence": 0.0-1.0
  }}
]}}
"""
            else:
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

    async def _extract_cultivation_system(
        self,
        content: str,
        series_id: int
    ) -> Dict[str, Any]:
        """Extract cultivation/power system from document."""

        prompt = f"""Extract the CULTIVATION/POWER SYSTEM from this story setting.

TEXT:
{content[:8000]}

Look for:
- Cultivation realms/levels (境界) and their names
- Requirements for each level
- Talent types (天赋/灵根)
- Special abilities gained at each level
- System rules and limitations

JSON response:
{{
    "system_name": "Name of the cultivation system",
    "realms": [
        {{
            "tier": 1,
            "name": "Realm Name",
            "chinese_name": "境界中文名",
            "description": "What this realm represents",
            "requirements": "What's needed to reach this",
            "abilities": ["abilities gained"]
        }}
    ],
    "talent_types": [
        {{
            "category": "Talent Category",
            "description": "What this talent type is",
            "examples": ["example1", "example2"]
        }}
    ],
    "special_rules": [
        "Rule about the cultivation system"
    ]
}}
"""

        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        try:
            cultivation_system = self._extract_json(response)

            # Save realms to knowledge base
            from app.database.qdrant_client import get_vector_manager
            from app.services.embeddings import generate_embedding

            async with AsyncSessionLocal() as db:
                for realm in cultivation_system.get("realms", []):
                    realm_content = f"""境界：{realm.get('name', '')} ({realm.get('chinese_name', '')})
第{realm.get('tier', 0)}境

{realm.get('description', '')}

要求：{realm.get('requirements', '')}

能力：{', '.join(realm.get('abilities', []))}
"""
                    embedding = generate_embedding(realm_content)

                    await db.execute(
                        text("""
                            INSERT INTO knowledge_base
                            (source_type, category, title, content, language, embedding, tags, metadata)
                            VALUES ('extracted', 'cultivation_realm', :title, :content, 'zh-CN',
                                    :embedding, :tags, :metadata)
                        """),
                        {
                            "title": f"境界：{realm.get('name', '')}",
                            "content": realm_content,
                            "embedding": str(embedding),
                            "tags": ["cultivation", "realm", f"tier_{realm.get('tier', 0)}", f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "tier": realm.get("tier"),
                                "auto_extracted": True
                            })
                        }
                    )

                await db.commit()

            return cultivation_system

        except Exception as e:
            logger.warning(f"Cultivation system extraction failed: {e}")
            return {}

    async def _extract_story_parts_with_reconciliation(
        self,
        content: str,
        series_id: int,
        reconciliation: Optional[Dict] = None
    ) -> List[Dict]:
        """Extract story parts/books structure using reconciliation data."""

        # Build context from reconciliation
        recon_context = ""
        if reconciliation:
            story_struct = reconciliation.get("story_structure", {})
            recon_info = reconciliation.get("reconciliation", {})

            if recon_info:
                recon_context = f"""
RECONCILIATION DATA (use this to guide extraction):
- Total main parts: {recon_info.get('total_main_parts', 'unknown')}
- Has prequel parts: {recon_info.get('has_prequel_parts', False)}
- Prequel parts: {recon_info.get('prequel_parts', [])}
- Timeline order: {recon_info.get('timeline_order', 'unknown')}

Main story structure from reconciliation:
"""
                for part in story_struct.get("main_parts", []):
                    recon_context += f"- Part {part.get('part_number')}: {part.get('title')} ({part.get('era', '')})\n"
                    recon_context += f"  Protagonists: {', '.join(part.get('main_protagonists', []))}\n"

                if story_struct.get("spinoffs"):
                    recon_context += "\nSpinoffs:\n"
                    for spinoff in story_struct.get("spinoffs", []):
                        recon_context += f"- {spinoff.get('title')}: {spinoff.get('main_character')}\n"

        prompt = f"""Extract STORY PARTS/BOOKS structure from this setting document.
{recon_context}

TEXT:
{content[:10000]}

Look for:
- Story parts (第一部, 第二部, etc.)
- Book titles and subtitles
- Main protagonists and antagonists for each part
- Key events and plot points
- Timeline information

JSON response:
{{"story_parts": [
    {{
        "part_number": 1,
        "title": "Part Title",
        "subtitle": "Part Subtitle",
        "timeline": "When this part takes place",
        "protagonists": ["protagonist1", "protagonist2"],
        "antagonists": ["antagonist1"],
        "summary": "Brief summary of this part",
        "key_events": ["event1", "event2", "event3"],
        "themes": ["theme1", "theme2"]
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
            story_parts = data.get("story_parts", [])

            async with AsyncSessionLocal() as db:
                for part in story_parts:
                    if not part.get("title"):
                        continue

                    # Create as a book entry
                    result = await db.execute(
                        text("""
                            INSERT INTO books
                            (series_id, book_number, title, theme, synopsis, verification_status, metadata)
                            VALUES (:series_id, :book_number, :title, :theme, :synopsis, 'pending', :metadata)
                            ON CONFLICT (series_id, book_number) DO UPDATE
                            SET title = EXCLUDED.title, theme = EXCLUDED.theme, synopsis = EXCLUDED.synopsis
                            RETURNING id, title
                        """),
                        {
                            "series_id": series_id,
                            "book_number": part.get("part_number", 1),
                            "title": f"{part.get('title', '')} - {part.get('subtitle', '')}",
                            "theme": ", ".join(part.get("themes", [])),
                            "synopsis": part.get("summary", ""),
                            "metadata": json.dumps({
                                "timeline": part.get("timeline"),
                                "protagonists": part.get("protagonists", []),
                                "antagonists": part.get("antagonists", []),
                                "key_events": part.get("key_events", []),
                                "auto_extracted": True
                            })
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "title": row.title,
                            "part_number": part.get("part_number", 1)
                        })

                await db.commit()

        except Exception as e:
            logger.warning(f"Story parts extraction failed: {e}")

        return created

    async def _extract_concepts(
        self,
        content: str,
        series_id: int
    ) -> List[Dict]:
        """Extract key concepts and terminology from document."""

        chunks = self._chunk_for_extraction(content, 6000)
        all_concepts = []

        for chunk in chunks[:5]:
            prompt = f"""Extract KEY CONCEPTS and TERMINOLOGY from this story setting.

TEXT:
{chunk}

Look for:
- Unique terminology and proper nouns
- Power/ability names
- Techniques and skills
- Artifacts and items
- Organizations and factions
- Philosophical concepts
- Historical events (as concepts)

JSON response:
{{"concepts": [
    {{
        "name": "Concept Name",
        "type": "term|technique|artifact|organization|philosophy|power|event|other",
        "definition": "What this concept means in the story",
        "importance": "critical|major|normal|minor",
        "related_to": ["related concept names"],
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
                all_concepts.extend(data.get("concepts", []))
            except Exception as e:
                logger.warning(f"Concept extraction chunk failed: {e}")

        # Deduplicate by name
        seen_names = set()
        unique_concepts = []
        for concept in all_concepts:
            name = concept.get("name", "").lower()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_concepts.append(concept)

        # Save to knowledge base
        created = []
        from app.database.qdrant_client import get_vector_manager

        async with AsyncSessionLocal() as db:
            for concept in unique_concepts:
                if not concept.get("name") or not concept.get("definition"):
                    continue

                try:
                    embedding = generate_embedding(
                        f"{concept.get('name', '')} {concept.get('definition', '')}"
                    )

                    result = await db.execute(
                        text("""
                            INSERT INTO knowledge_base
                            (source_type, category, title, content, language, embedding, tags, metadata)
                            VALUES ('extracted', :category, :title, :content, 'zh-CN',
                                    :embedding, :tags, :metadata)
                            RETURNING id
                        """),
                        {
                            "category": concept.get("type", "concept"),
                            "title": concept.get("name"),
                            "content": concept.get("definition", ""),
                            "embedding": str(embedding),
                            "tags": [concept.get("type", "concept"), f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "importance": concept.get("importance"),
                                "related_to": concept.get("related_to", []),
                                "auto_extracted": True
                            })
                        }
                    )
                    row = result.fetchone()
                    if row:
                        created.append({
                            "id": row.id,
                            "name": concept.get("name"),
                            "type": concept.get("type"),
                            "confidence": concept.get("confidence", 0.7)
                        })
                except Exception as e:
                    logger.warning(f"Failed to save concept {concept.get('name')}: {e}")

            await db.commit()

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

