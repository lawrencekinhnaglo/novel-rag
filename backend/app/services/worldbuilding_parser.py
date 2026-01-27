"""
Specialized Worldbuilding Document Parser

Parses structured Chinese novel worldbuilding documents with sections like:
- 口徑與命名規範 (Naming conventions)
- 時間線與代際框架 (Timeline and generations)
- 核心世界觀 (Core worldview)
- 修行體系 (Cultivation system)
- 核心器物與技術總表 (Artifacts and technology)
- 陣營與勢力總覽 (Factions and forces)
- 正傳/外傳/前傳 (Main story, spinoffs, prequels)
- 伏筆回收總表 (Foreshadowing recovery)

This parser is designed to handle documents like《牧羊紀元：道果牧場》統一設定文檔
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

from app.services.llm_service import get_llm_service
from app.services.embeddings import generate_embedding
from app.database.postgres import AsyncSessionLocal
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BookType(Enum):
    MAIN = "main"  # 正傳
    SPINOFF = "spinoff"  # 外傳
    PREQUEL = "prequel"  # 前傳/牧場編年史


@dataclass
class StoryPart:
    """Represents a story part (book/volume)."""
    part_number: int
    title: str
    subtitle: str = ""
    book_type: str = "main"
    era: str = ""
    timeline: str = ""
    protagonists: List[str] = field(default_factory=list)
    antagonists: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    genre_style: str = ""
    logline: str = ""
    three_act_summary: Dict[str, str] = field(default_factory=dict)
    key_scenes: List[str] = field(default_factory=list)
    growth_arc: Dict[str, str] = field(default_factory=dict)
    foreshadowing_planted: List[str] = field(default_factory=list)
    foreshadowing_recovered: List[str] = field(default_factory=list)


@dataclass
class Character:
    """Represents a character."""
    name: str
    aliases: List[str] = field(default_factory=list)
    role: str = "supporting"  # protagonist, antagonist, supporting, minor
    generation: str = ""  # 第1代, 第2代, etc.
    faction: str = ""
    description: str = ""
    personality: str = ""
    abilities: List[str] = field(default_factory=list)
    background: str = ""
    goals: str = ""
    growth_arc: str = ""
    relationships: List[Dict[str, str]] = field(default_factory=list)
    first_appears_in: int = 1
    confidence: float = 0.9


@dataclass 
class Artifact:
    """Represents a core artifact/item."""
    name: str
    aliases: List[str] = field(default_factory=list)
    artifact_type: str = ""  # 神器, 法寶, 容器, 武器, etc.
    first_appearance: int = 0  # Book number
    core_function: str = ""
    ultimate_purpose: str = ""
    related_characters: List[str] = field(default_factory=list)


@dataclass
class CultivationRealm:
    """Represents a cultivation realm."""
    tier: int
    name: str
    group_name: str = ""  # 凡人三境, 超凡三境, etc.
    description: str = ""
    question: str = ""  # 叩問
    requirements: str = ""
    abilities: List[str] = field(default_factory=list)
    harvest_risk: str = ""  # 收割紅線 level


@dataclass
class Foreshadowing:
    """Represents a foreshadowing element."""
    title: str
    planted_in: int  # Book number
    recovered_in: int  # Book number
    planted_text: str = ""
    recovery_method: str = ""
    cross_book: bool = True


@dataclass
class WorldbuildingDocument:
    """Complete parsed worldbuilding document."""
    title: str
    version: str = ""
    series_info: Dict[str, Any] = field(default_factory=dict)
    
    # Naming conventions
    naming_conventions: Dict[str, Any] = field(default_factory=dict)
    
    # Timeline
    timeline: Dict[str, Any] = field(default_factory=dict)
    
    # World view
    core_worldview: Dict[str, Any] = field(default_factory=dict)
    
    # World map
    world_map: Dict[str, Any] = field(default_factory=dict)
    
    # Cultivation system
    cultivation_system: Dict[str, Any] = field(default_factory=dict)
    cultivation_realms: List[CultivationRealm] = field(default_factory=list)
    
    # Artifacts
    artifacts: List[Artifact] = field(default_factory=list)
    
    # Factions
    factions: Dict[str, Any] = field(default_factory=dict)
    
    # Story parts
    main_story: List[StoryPart] = field(default_factory=list)  # 正傳 1-6
    spinoffs: List[StoryPart] = field(default_factory=list)  # 外傳
    prequels: List[StoryPart] = field(default_factory=list)  # 前傳 7-11
    
    # Characters
    characters: List[Character] = field(default_factory=list)
    
    # Foreshadowing
    foreshadowing: List[Foreshadowing] = field(default_factory=list)
    
    # Rules
    rules: List[Dict[str, Any]] = field(default_factory=list)
    
    # Raw sections for reference
    raw_sections: Dict[str, str] = field(default_factory=dict)


class WorldbuildingParser:
    """
    Parser for structured worldbuilding documents.
    
    Workflow:
    1. Parse document structure (headers, sections)
    2. Extract each section with specialized prompts
    3. Build comprehensive worldbuilding data
    4. Save to database with proper relationships
    """
    
    # Section patterns for Chinese worldbuilding docs
    SECTION_PATTERNS = [
        (r'[一二三四五六七八九十]+[)）]\s*(.+)', 'numbered_chinese'),
        (r'(\d+)[)）.]\s*(.+)', 'numbered_arabic'),
        (r'[第]([一二三四五六七八九十\d]+)[部卷章節]', 'story_part'),
        (r'#+\s*(.+)', 'markdown'),
        (r'【(.+?)】', 'bracket'),
    ]
    
    def __init__(self, provider: str = None):
        self.llm = get_llm_service(provider)
    
    def parse_structure(self, content: str) -> Dict[str, str]:
        """
        Parse document into sections based on headers.
        Returns dict mapping section titles to their content.
        """
        sections = {}
        current_section = "intro"
        current_content = []
        
        lines = content.split('\n')
        
        for line in lines:
            # Check for section headers
            is_header = False
            section_title = None
            
            # Chinese numbered sections: 1) 口徑與命名規範
            match = re.match(r'^(\d+)[)）]\s*(.+)$', line.strip())
            if match:
                is_header = True
                section_title = match.group(2).strip()
            
            # Markdown headers
            if not is_header:
                match = re.match(r'^#{1,3}\s*(.+)$', line.strip())
                if match:
                    is_header = True
                    section_title = match.group(1).strip()
            
            # 第X部 pattern
            if not is_header:
                match = re.match(r'^第[一二三四五六七八九十\d]+部[《〈]?(.+?)[》〉]?', line.strip())
                if match:
                    is_header = True
                    section_title = line.strip()
            
            if is_header and section_title:
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = section_title
                current_content = []
            else:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
    
    async def parse_document(self, content: str, filename: str = "") -> WorldbuildingDocument:
        """
        Parse a complete worldbuilding document.
        
        Returns a structured WorldbuildingDocument object.
        """
        # Initialize result
        doc = WorldbuildingDocument(title=filename.rsplit('.', 1)[0] if filename else "Untitled")
        
        # Parse structure
        sections = self.parse_structure(content)
        doc.raw_sections = sections
        
        # Extract document metadata
        doc.title, doc.version = self._extract_title_version(content)
        
        # Process each section type
        await self._extract_story_parts(content, doc)
        await self._extract_characters(content, doc)
        await self._extract_cultivation_system(content, doc)
        await self._extract_artifacts(content, doc)
        await self._extract_foreshadowing(content, doc)
        await self._extract_world_rules(content, doc)
        await self._extract_core_worldview(content, doc)
        
        return doc
    
    def _extract_title_version(self, content: str) -> Tuple[str, str]:
        """Extract document title and version."""
        title = "Unknown"
        version = ""
        
        # Look for title pattern like《牧羊紀元：道果牧場》
        match = re.search(r'[《「](.+?)[》」]', content[:500])
        if match:
            title = match.group(1)
        
        # Look for version pattern like v3.0
        match = re.search(r'[vV]?(\d+\.\d+)', content[:500])
        if match:
            version = f"v{match.group(1)}"
        
        return title, version
    
    async def _extract_story_parts(self, content: str, doc: WorldbuildingDocument):
        """Extract story parts (main, spinoffs, prequels)."""
        
        prompt = f"""Analyze this worldbuilding document and extract ALL STORY PARTS/BOOKS.

DOCUMENT (first 15000 chars):
{content[:15000]}

This document describes a novel series with:
- Main story (正傳): Parts 1-6
- Spinoffs (外傳): Like《北海聽劍人》
- Prequels (前傳/牧場編年史): Parts 7-11

For EACH story part found, extract:
- part_number: The part/book number
- title: Chinese title
- subtitle: If available
- book_type: "main", "spinoff", or "prequel"
- era: Time period (e.g., 仙古, 荒古)
- protagonists: Main character names for this part
- antagonists: Main antagonist names
- themes: Key themes
- genre_style: Genre/style reference (e.g., "古典仙俠 + 宿命悲劇")
- logline: One-sentence summary
- three_act_summary: Brief 3-act structure if available
- key_scenes: Important scenes/名場面
- growth_arc: Character growth trajectory

Return ONLY valid JSON:
{{
    "main_story": [
        {{
            "part_number": 1,
            "title": "Part Title",
            "subtitle": "Subtitle",
            "book_type": "main",
            "era": "",
            "protagonists": ["name1", "name2"],
            "antagonists": ["name1"],
            "themes": ["theme1", "theme2"],
            "genre_style": "古典仙俠 + 宿命悲劇",
            "logline": "One sentence summary",
            "three_act_summary": {{"act1": "", "act2": "", "act3": ""}},
            "key_scenes": ["scene1", "scene2"],
            "growth_arc": {{"start": "", "transition": "", "end": ""}}
        }}
    ],
    "spinoffs": [...],
    "prequels": [...]
}}
"""
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            data = self._extract_json(response)
            
            # Parse main story parts
            for part_data in data.get("main_story", []):
                doc.main_story.append(StoryPart(
                    part_number=part_data.get("part_number", 1),
                    title=part_data.get("title", ""),
                    subtitle=part_data.get("subtitle", ""),
                    book_type="main",
                    era=part_data.get("era", ""),
                    protagonists=part_data.get("protagonists", []),
                    antagonists=part_data.get("antagonists", []),
                    themes=part_data.get("themes", []),
                    genre_style=part_data.get("genre_style", ""),
                    logline=part_data.get("logline", ""),
                    three_act_summary=part_data.get("three_act_summary", {}),
                    key_scenes=part_data.get("key_scenes", [])
                ))
            
            # Parse spinoffs
            for part_data in data.get("spinoffs", []):
                doc.spinoffs.append(StoryPart(
                    part_number=part_data.get("part_number", 0),
                    title=part_data.get("title", ""),
                    subtitle=part_data.get("subtitle", ""),
                    book_type="spinoff",
                    era=part_data.get("era", ""),
                    protagonists=part_data.get("protagonists", []),
                    antagonists=part_data.get("antagonists", []),
                    themes=part_data.get("themes", [])
                ))
            
            # Parse prequels
            for part_data in data.get("prequels", []):
                doc.prequels.append(StoryPart(
                    part_number=part_data.get("part_number", 7),
                    title=part_data.get("title", ""),
                    subtitle=part_data.get("subtitle", ""),
                    book_type="prequel",
                    era=part_data.get("era", ""),
                    protagonists=part_data.get("protagonists", []),
                    antagonists=part_data.get("antagonists", []),
                    themes=part_data.get("themes", [])
                ))
                
        except Exception as e:
            logger.error(f"Story parts extraction failed: {e}")
    
    async def _extract_characters(self, content: str, doc: WorldbuildingDocument):
        """Extract all characters with their generation/faction info."""
        
        # Process in chunks for large documents
        chunks = self._chunk_content(content, 8000)
        all_characters = []
        seen_names = set()
        
        for chunk in chunks[:6]:  # Process up to 6 chunks
            prompt = f"""Extract ALL CHARACTERS from this worldbuilding document.

TEXT:
{chunk}

For each character, extract:
- name: Primary name
- aliases: Other names, titles, nicknames (道號, 別名)
- role: protagonist | antagonist | supporting | minor
- generation: Which generation (第1代, 第2代, etc.) - based on when they are main character
- faction: 反抗陣營 | 天命/天律殘響 | 牧者 | other
- description: Full description
- personality: Personality traits
- abilities: Powers, talents, special abilities (list)
- background: History/backstory
- goals: What they want to achieve
- growth_arc: Their character development journey
- relationships: Key relationships (list of {{target, type, description}})
- first_appears_in: Part number where they first appear prominently

IMPORTANT: Pay attention to 代際 (generations):
- 第1代: Part 1 main characters (袁長生, 君天命)
- 第2代: Part 2 main characters (況淳風, 墨千機)
- 第3代: Part 3 main characters (凌絕, 葉留白)
- etc.

Return ONLY valid JSON:
{{
    "characters": [
        {{
            "name": "Character Name",
            "aliases": ["alias1", "道號"],
            "role": "protagonist",
            "generation": "第1代",
            "faction": "反抗陣營",
            "description": "...",
            "personality": "...",
            "abilities": ["ability1", "ability2"],
            "background": "...",
            "goals": "...",
            "growth_arc": "...",
            "relationships": [{{"target": "Other", "type": "師徒", "description": "..."}}],
            "first_appears_in": 1,
            "confidence": 0.9
        }}
    ]
}}
"""
            
            try:
                response = await self.llm.generate(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                
                data = self._extract_json(response)
                
                for char_data in data.get("characters", []):
                    name = char_data.get("name", "")
                    if name and name.lower() not in seen_names:
                        seen_names.add(name.lower())
                        all_characters.append(Character(
                            name=name,
                            aliases=char_data.get("aliases", []),
                            role=char_data.get("role", "supporting"),
                            generation=char_data.get("generation", ""),
                            faction=char_data.get("faction", ""),
                            description=char_data.get("description", ""),
                            personality=char_data.get("personality", ""),
                            abilities=char_data.get("abilities", []),
                            background=char_data.get("background", ""),
                            goals=char_data.get("goals", ""),
                            growth_arc=char_data.get("growth_arc", ""),
                            relationships=char_data.get("relationships", []),
                            first_appears_in=char_data.get("first_appears_in", 1),
                            confidence=char_data.get("confidence", 0.8)
                        ))
                        
            except Exception as e:
                logger.warning(f"Character extraction chunk failed: {e}")
        
        doc.characters = all_characters
    
    async def _extract_cultivation_system(self, content: str, doc: WorldbuildingDocument):
        """Extract cultivation system with 15 realms."""
        
        prompt = f"""Extract the CULTIVATION SYSTEM (修行體系) from this document.

TEXT:
{content[:12000]}

This document describes a 15-realm (十五境) cultivation system organized in groups:
- 凡人三境: Mortal realms
- 超凡三境: Transcendent realms  
- 登仙三境: Ascension realms
- 仙業三境: Immortal realms
- 問道三境: Dao realms

Also extract the 收割紅線 (Harvest Red Line) system:
- 安全區: Safe zone
- 監控區: Monitoring zone
- 屠宰區: Slaughter zone

Return ONLY valid JSON:
{{
    "system_name": "十五境修行體系",
    "realm_groups": [
        {{
            "name": "凡人三境",
            "realms": [
                {{
                    "tier": 1,
                    "name": "凝氣",
                    "question": "汝道為何？",
                    "description": "...",
                    "harvest_risk": "安全區"
                }}
            ]
        }}
    ],
    "harvest_system": {{
        "safe_zone": "description of safe zone",
        "monitor_zone": "description of monitoring zone", 
        "slaughter_zone": "description of slaughter zone"
    }},
    "special_rules": [
        "Rule about the cultivation system"
    ]
}}
"""
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            data = self._extract_json(response)
            doc.cultivation_system = data
            
            # Also create flat realm list
            for group in data.get("realm_groups", []):
                group_name = group.get("name", "")
                for realm_data in group.get("realms", []):
                    doc.cultivation_realms.append(CultivationRealm(
                        tier=realm_data.get("tier", 0),
                        name=realm_data.get("name", ""),
                        group_name=group_name,
                        description=realm_data.get("description", ""),
                        question=realm_data.get("question", ""),
                        harvest_risk=realm_data.get("harvest_risk", "")
                    ))
                    
        except Exception as e:
            logger.error(f"Cultivation system extraction failed: {e}")
    
    async def _extract_artifacts(self, content: str, doc: WorldbuildingDocument):
        """Extract core artifacts and items (核心器物與技術總表)."""
        
        prompt = f"""Extract the CORE ARTIFACTS AND TECHNOLOGY (核心器物與技術總表) from this document.

TEXT:
{content[:12000]}

Look for important items like:
- 陰陽雙龍玉 (輪回雙魚玉佩)
- 欺天棺
- 神源
- 劍冢
- 補天針
- 黑鐵方舟
- 墨家機關城
- 墨焱劍
- 八獸賜福

For each artifact extract:
- name: Primary name
- aliases: Other names
- artifact_type: 神器/容器 | 火種容器 | 本命物 | 移動堡壘 | 勢力/遺產 | 合體之劍 | 體系/模組
- first_appearance: Book number where first appears
- core_function: Main function/purpose
- ultimate_purpose: Final/ultimate use in story
- related_characters: Characters associated with this item

Return ONLY valid JSON:
{{
    "artifacts": [
        {{
            "name": "陰陽雙龍玉",
            "aliases": ["輪回雙魚玉佩", "雙魚玉佩"],
            "artifact_type": "神器/容器",
            "first_appearance": 1,
            "core_function": "靈魂硬碟、殘魂寄宿、跨代資訊封存",
            "ultimate_purpose": "第4部復活關鍵；第3部真相來源",
            "related_characters": ["袁長生", "君天命"]
        }}
    ]
}}
"""
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            data = self._extract_json(response)
            
            for artifact_data in data.get("artifacts", []):
                doc.artifacts.append(Artifact(
                    name=artifact_data.get("name", ""),
                    aliases=artifact_data.get("aliases", []),
                    artifact_type=artifact_data.get("artifact_type", ""),
                    first_appearance=artifact_data.get("first_appearance", 0),
                    core_function=artifact_data.get("core_function", ""),
                    ultimate_purpose=artifact_data.get("ultimate_purpose", ""),
                    related_characters=artifact_data.get("related_characters", [])
                ))
                
        except Exception as e:
            logger.error(f"Artifacts extraction failed: {e}")
    
    async def _extract_foreshadowing(self, content: str, doc: WorldbuildingDocument):
        """Extract foreshadowing table (伏筆回收總表)."""
        
        prompt = f"""Extract the FORESHADOWING TABLE (伏筆回收總表) from this document.

TEXT:
{content[:12000]}

Look for a table or list of foreshadowing elements with:
- What was planted (伏筆/資產)
- Where it was planted (埋下位置)
- Where it was recovered (回收位置)
- How it was recovered (回收方式)

Return ONLY valid JSON:
{{
    "foreshadowing": [
        {{
            "title": "長生體不是恩賜",
            "planted_in": 1,
            "planted_text": "第1部疑雲",
            "recovered_in": 9,
            "recovery_method": "奴隸印記 + 手術論鐵證"
        }}
    ]
}}
"""
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            data = self._extract_json(response)
            
            for fs_data in data.get("foreshadowing", []):
                doc.foreshadowing.append(Foreshadowing(
                    title=fs_data.get("title", ""),
                    planted_in=fs_data.get("planted_in", 0),
                    planted_text=fs_data.get("planted_text", ""),
                    recovered_in=fs_data.get("recovered_in", 0),
                    recovery_method=fs_data.get("recovery_method", "")
                ))
                
        except Exception as e:
            logger.error(f"Foreshadowing extraction failed: {e}")
    
    async def _extract_world_rules(self, content: str, doc: WorldbuildingDocument):
        """Extract world rules including《天律網》rules."""
        
        prompt = f"""Extract WORLD RULES from this document, including《天律網》rules.

TEXT:
{content[:10000]}

Look for:
- Core world concepts (牧羊紀元, 道果牧場, 收割機制)
- 天律網規則 (萬物皆應有約, 萬約皆必履行, 違約必受天刑)
- Specific law articles (天律·追索條, 天律·連坐條, etc.)

Return ONLY valid JSON:
{{
    "rules": [
        {{
            "category": "core_worldview | harvest_mechanism | tianlu_principle | tianlu_article | society | magic",
            "name": "Rule Name",
            "description": "Full description",
            "is_hard_rule": true,
            "exceptions": [],
            "source": "Where this rule is established"
        }}
    ]
}}
"""
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            data = self._extract_json(response)
            doc.rules = data.get("rules", [])
                
        except Exception as e:
            logger.error(f"World rules extraction failed: {e}")
    
    async def _extract_core_worldview(self, content: str, doc: WorldbuildingDocument):
        """Extract core worldview concepts."""
        
        prompt = f"""Extract the CORE WORLDVIEW (核心世界觀) from this document.

TEXT:
{content[:10000]}

Look for:
- 道果牧場 concept (world as a farm)
- 牧者生態圖譜 (Shepherd hierarchy: 巡林客, 屠夫, 美食家)
- 美食家理論 (why shepherds don't destroy immediately)
- 世界地圖 (巨人的屍骸 - world as a corpse)
- 反抗主軸 evolution across parts

Return ONLY valid JSON:
{{
    "core_concepts": {{
        "world_nature": "道果牧場 - world is a fruit farm for higher beings",
        "surgery_metaphor": "反抗 = cutting off slave marks",
        "harvest_mechanism": "When civilization shows maturity signals -> harvest",
        "resistance_evolution": ["復仇(1)", "存續(2)", "封閉探索(3)", "整合覺醒(4)", "遠征反收割(5-6)"]
    }},
    "shepherd_hierarchy": [
        {{
            "tier": "low",
            "name": "巡林客 (Grazers)",
            "function": "日常維護、清理雜草",
            "appearance": "無面目、機械化",
            "appears_in": [1, 2]
        }}
    ],
    "world_map": {{
        "concept": "巨人的屍骸",
        "locations": [
            {{
                "name": "北海冰眼",
                "body_part": "淚腺/眼睛",
                "function": "寒冷、封印、觀測世界的窗口",
                "story_relevance": "第3部葉留白被封印處"
            }}
        ]
    }}
}}
"""
        
        try:
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            doc.core_worldview = self._extract_json(response)
                
        except Exception as e:
            logger.error(f"Core worldview extraction failed: {e}")
    
    async def save_to_database(self, doc: WorldbuildingDocument, series_id: int = None) -> Dict[str, Any]:
        """
        Save parsed worldbuilding document to database.
        Uses separate transactions for each item to prevent cascading failures.
        
        Returns dict with created IDs for each category.
        """
        result = {
            "series_id": series_id,
            "books_created": [],
            "characters_created": [],
            "artifacts_created": [],
            "cultivation_realms_created": [],
            "foreshadowing_created": [],
            "world_rules_created": [],
            "knowledge_entries_created": [],
            "errors": []
        }
        
        # Step 1: Create or get series in its own transaction
        if not series_id:
            async with AsyncSessionLocal() as db:
                try:
                    series_result = await db.execute(
                        text("""
                            INSERT INTO series (title, premise, themes, language, metadata)
                            VALUES (:title, :premise, :themes, 'zh-TW', :metadata)
                            RETURNING id
                        """),
                        {
                            "title": doc.title,
                            "premise": doc.core_worldview.get("core_concepts", {}).get("world_nature", ""),
                            "themes": doc.core_worldview.get("core_concepts", {}).get("resistance_evolution", []),
                            "metadata": json.dumps({
                                "version": doc.version,
                                "auto_extracted": True,
                                "source": "worldbuilding_parser"
                            })
                        }
                    )
                    row = series_result.fetchone()
                    series_id = row.id
                    result["series_id"] = series_id
                    await db.commit()
                    logger.info(f"Created series: {doc.title} with ID {series_id}")
                except Exception as e:
                    logger.error(f"Failed to create series: {e}")
                    result["errors"].append(f"Series creation: {str(e)}")
                    return result
        
        # Step 2: Save books (each in separate transaction)
        all_parts = doc.main_story + doc.spinoffs + doc.prequels
        spinoff_counter = -1  # Use negative numbers for spinoffs without part_number
        
        for part in all_parts:
            async with AsyncSessionLocal() as db:
                try:
                    # Handle NULL book_number for spinoffs by using negative numbers
                    book_number = part.part_number
                    if book_number is None:
                        book_number = spinoff_counter
                        spinoff_counter -= 1
                    
                    book_result = await db.execute(
                        text("""
                            INSERT INTO books 
                            (series_id, book_number, title, theme, synopsis, status, metadata)
                            VALUES (:series_id, :book_number, :title, :theme, :synopsis, 'planning', :metadata)
                            ON CONFLICT (series_id, book_number) DO UPDATE
                            SET title = EXCLUDED.title, theme = EXCLUDED.theme, synopsis = EXCLUDED.synopsis
                            RETURNING id, title
                        """),
                        {
                            "series_id": series_id,
                            "book_number": book_number,
                            "title": f"{part.title}" + (f" - {part.subtitle}" if part.subtitle else ""),
                            "theme": ", ".join(part.themes),
                            "synopsis": part.logline,
                            "metadata": json.dumps({
                                "book_type": part.book_type,
                                "era": part.era,
                                "protagonists": part.protagonists,
                                "antagonists": part.antagonists,
                                "genre_style": part.genre_style,
                                "three_act_summary": part.three_act_summary,
                                "key_scenes": part.key_scenes,
                                "auto_extracted": True
                            })
                        }
                    )
                    row = book_result.fetchone()
                    await db.commit()
                    if row:
                        result["books_created"].append({"id": row.id, "title": row.title})
                        logger.info(f"Saved book: {row.title}")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Book {part.part_number}: {str(e)}")
                
        # Step 3: Save characters (each in separate transaction)
        for char in doc.characters:
            async with AsyncSessionLocal() as db:
                try:
                    description = char.description
                    if char.personality:
                        description += f"\n\n**性格**: {char.personality}"
                    if char.abilities:
                        description += f"\n\n**能力**: {', '.join(char.abilities)}"
                    if char.growth_arc:
                        description += f"\n\n**成長軌跡**: {char.growth_arc}"
                    
                    embedding = generate_embedding(f"{char.name} {description[:500]}")
                    
                    char_result = await db.execute(
                        text("""
                            INSERT INTO character_profiles
                            (series_id, name, aliases, description, personality, background, goals,
                             first_appearance_book, embedding, language, verification_status, auto_extracted, metadata)
                            VALUES (:series_id, :name, :aliases, :description, :personality, :background, :goals,
                                    :first_appearance, :embedding, 'zh-TW', 'pending', TRUE, :metadata)
                            ON CONFLICT (series_id, name) DO UPDATE
                            SET description = EXCLUDED.description, aliases = EXCLUDED.aliases
                            RETURNING id, name
                        """),
                        {
                            "series_id": series_id,
                            "name": char.name,
                            "aliases": char.aliases,
                            "description": description,
                            "personality": char.personality,
                            "background": char.background,
                            "goals": char.goals,
                            "first_appearance": char.first_appears_in,
                            "embedding": str(embedding),
                            "metadata": json.dumps({
                                "role": char.role,
                                "generation": char.generation,
                                "faction": char.faction,
                                "abilities": char.abilities,
                                "relationships": char.relationships,
                                "confidence": char.confidence
                            })
                        }
                    )
                    row = char_result.fetchone()
                    await db.commit()
                    if row:
                        result["characters_created"].append({"id": row.id, "name": row.name})
                        logger.info(f"Saved character: {row.name}")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Character {char.name}: {str(e)}")
                
        # Step 4: Save cultivation realms to knowledge base
        for realm in doc.cultivation_realms:
            async with AsyncSessionLocal() as db:
                try:
                    content = f"""境界：{realm.name}
第{realm.tier}境 ({realm.group_name})

{realm.description}

叩問：{realm.question}

收割風險：{realm.harvest_risk}
"""
                    embedding = generate_embedding(content)
                    
                    await db.execute(
                        text("""
                            INSERT INTO knowledge_base
                            (source_type, category, title, content, language, embedding, tags, metadata)
                            VALUES ('extracted', 'cultivation_realm', :title, :content, 'zh-TW',
                                    :embedding, :tags, :metadata)
                        """),
                        {
                            "title": f"境界：{realm.name}",
                            "content": content,
                            "embedding": str(embedding),
                            "tags": ["cultivation", "realm", realm.group_name, f"tier_{realm.tier}", f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "tier": realm.tier,
                                "harvest_risk": realm.harvest_risk,
                                "auto_extracted": True
                            })
                        }
                    )
                    await db.commit()
                    result["cultivation_realms_created"].append(realm.name)
                    logger.info(f"Saved cultivation realm: {realm.name}")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Realm {realm.name}: {str(e)}")
        
        # Step 5: Save artifacts to knowledge base
        for artifact in doc.artifacts:
            async with AsyncSessionLocal() as db:
                try:
                    content = f"""器物：{artifact.name}
別名：{', '.join(artifact.aliases)}
類型：{artifact.artifact_type}

核心功能：{artifact.core_function}

最終用途：{artifact.ultimate_purpose}

相關角色：{', '.join(artifact.related_characters)}

首次出場：第{artifact.first_appearance}部
"""
                    embedding = generate_embedding(content)
                    
                    await db.execute(
                        text("""
                            INSERT INTO knowledge_base
                            (source_type, category, title, content, language, embedding, tags, metadata)
                            VALUES ('extracted', 'artifact', :title, :content, 'zh-TW',
                                    :embedding, :tags, :metadata)
                        """),
                        {
                            "title": f"器物：{artifact.name}",
                            "content": content,
                            "embedding": str(embedding),
                            "tags": ["artifact", artifact.artifact_type, f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "first_appearance": artifact.first_appearance,
                                "aliases": artifact.aliases,
                                "auto_extracted": True
                            })
                        }
                    )
                    await db.commit()
                    result["artifacts_created"].append(artifact.name)
                    logger.info(f"Saved artifact: {artifact.name}")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Artifact {artifact.name}: {str(e)}")
        
        # Step 6: Save foreshadowing
        for fs in doc.foreshadowing:
            async with AsyncSessionLocal() as db:
                try:
                    await db.execute(
                        text("""
                            INSERT INTO foreshadowing
                            (series_id, title, planted_book, planted_text, payoff_book, payoff_text,
                             seed_type, status, verification_status, auto_extracted)
                            VALUES (:series_id, :title, :planted_book, :planted_text, :payoff_book, :payoff_text,
                                    'plot', 'paid_off', 'pending', TRUE)
                        """),
                        {
                            "series_id": series_id,
                            "title": fs.title,
                            "planted_book": fs.planted_in,
                            "planted_text": fs.planted_text,
                            "payoff_book": fs.recovered_in,
                            "payoff_text": fs.recovery_method
                        }
                    )
                    await db.commit()
                    result["foreshadowing_created"].append(fs.title)
                    logger.info(f"Saved foreshadowing: {fs.title}")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Foreshadowing {fs.title}: {str(e)}")
        
        # Step 7: Save world rules
        for rule in doc.rules:
            async with AsyncSessionLocal() as db:
                try:
                    await db.execute(
                        text("""
                            INSERT INTO world_rules
                            (series_id, rule_category, rule_name, rule_description, is_hard_rule,
                             exceptions, verification_status, auto_extracted)
                            VALUES (:series_id, :category, :name, :description, :is_hard,
                                    :exceptions, 'pending', TRUE)
                        """),
                        {
                            "series_id": series_id,
                            "category": rule.get("category", "other"),
                            "name": rule.get("name", ""),
                            "description": rule.get("description", ""),
                            "is_hard": rule.get("is_hard_rule", True),
                            "exceptions": rule.get("exceptions", [])
                        }
                    )
                    await db.commit()
                    result["world_rules_created"].append(rule.get("name"))
                    logger.info(f"Saved world rule: {rule.get('name')}")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Rule {rule.get('name')}: {str(e)}")
        
        # Step 8: Save core worldview as knowledge entry
        if doc.core_worldview:
            async with AsyncSessionLocal() as db:
                try:
                    worldview_content = json.dumps(doc.core_worldview, ensure_ascii=False, indent=2)
                    embedding = generate_embedding(worldview_content[:2000])
                    
                    await db.execute(
                        text("""
                            INSERT INTO knowledge_base
                            (source_type, category, title, content, language, embedding, tags, metadata)
                            VALUES ('extracted', 'world_concept', :title, :content, 'zh-TW',
                                    :embedding, :tags, :metadata)
                        """),
                        {
                            "title": f"{doc.title} - 核心世界觀",
                            "content": worldview_content,
                            "embedding": str(embedding),
                            "tags": ["worldview", "core_concept", f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "auto_extracted": True
                            })
                        }
                    )
                    await db.commit()
                    result["knowledge_entries_created"].append("核心世界觀")
                    logger.info("Saved core worldview")
                except Exception as e:
                    await db.rollback()
                    result["errors"].append(f"Worldview: {str(e)}")
        
        return result
    
    def _chunk_content(self, content: str, chunk_size: int = 8000) -> List[str]:
        """Split content into chunks."""
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
        # Try to find JSON block
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                # Try to fix common issues
                json_str = json_match.group()
                # Fix trailing commas
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                return json.loads(json_str)
        raise ValueError("No JSON found in response")


def get_worldbuilding_parser(provider: str = None) -> WorldbuildingParser:
    """Get worldbuilding parser instance."""
    return WorldbuildingParser(provider)
