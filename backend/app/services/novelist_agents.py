"""
Novelist Agent System - Multi-Agent Architecture for Long-Form Series Writers

This implements the vision of:
1. World Architect - Consistency checking, rule enforcement
2. Plot Strategist - Foreshadowing management, pacing analysis
3. Character Director - Character voice, relationship dynamics
4. Continuity Editor - Entity tracking, timeline management

These agents collaborate to help lazy novelists write amazing stories
while the AI handles all the tedious consistency work.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import logging
import re

logger = logging.getLogger(__name__)


# ==================== Data Models ====================

@dataclass
class ConsistencyIssue:
    """A detected consistency issue."""
    severity: str  # warning, error, critical
    category: str  # worldbuilding, character, timeline, object, rule
    description: str
    source_reference: str  # Where the original fact was established
    suggestion: str


@dataclass
class PlotThread:
    """A plot thread or foreshadowing element."""
    id: str
    title: str
    description: str
    planted_location: str  # "Book 1, Chapter 3"
    intended_payoff: Optional[str]  # "Book 7, Final chapter"
    status: str  # planted, developing, resolved, abandoned
    importance: str  # minor, major, critical
    related_characters: List[str] = field(default_factory=list)


@dataclass
class CharacterState:
    """Current state of a character."""
    name: str
    location: str
    emotional_state: str
    inventory: List[str]  # What they're carrying
    injuries: List[str]
    relationship_changes: Dict[str, str]  # {character: change_description}
    last_appearance: str  # "Chapter 5"


@dataclass
class EntityState:
    """State of an important object or entity."""
    name: str
    type: str  # weapon, artifact, location, etc.
    current_holder: Optional[str]
    location: str
    status: str  # intact, damaged, destroyed, lost
    last_mentioned: str


# ==================== World Architect Agent ====================

class WorldArchitectAgent:
    """
    The guardian of worldbuilding consistency.
    
    Responsibilities:
    - Check new content against established rules
    - Detect contradictions with worldbuilding
    - Enforce magic/power system rules
    - Validate historical/timeline consistency
    """
    
    def __init__(self, llm_service=None, db=None, rag_service=None):
        self.llm_service = llm_service
        self.db = db
        self.rag_service = rag_service
    
    async def check_consistency(self, 
                               new_content: str, 
                               series_id: int = None) -> List[ConsistencyIssue]:
        """
        Check new content against established worldbuilding.
        
        This is the core function that catches "eating the book" errors.
        """
        issues = []
        
        # Get relevant worldbuilding context
        worldbuilding = await self._get_worldbuilding_context(new_content, series_id)
        
        if not worldbuilding or not self.llm_service:
            return issues
        
        # Build the checking prompt
        worldbuilding_text = "\n".join([
            f"【{item.get('title', '')}】\n{item.get('content', '')}"
            for item in worldbuilding[:15]
        ])
        
        check_prompt = f"""你是一個世界觀一致性檢查專家。你的任務是找出新內容與已建立設定之間的矛盾。

【已建立的世界觀設定】
{worldbuilding_text}

【要檢查的新內容】
{new_content[:4000]}

請仔細分析，找出所有可能的矛盾。對於每個發現的問題，請按以下格式回答：

問題類型: [worldbuilding/character/timeline/object/rule]
嚴重程度: [warning/error/critical]
描述: [具體矛盾是什麼]
原設定出處: [在哪個設定中提到的]
建議修改: [如何修正]

如果沒有發現矛盾，請回答「無矛盾」。"""

        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個專業的小說編輯，專門負責檢查連載小說的設定一致性。"},
                    {"role": "user", "content": check_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            # Parse the response
            if "無矛盾" not in response:
                issues = self._parse_consistency_response(response)
                
        except Exception as e:
            logger.error(f"Consistency check failed: {e}")
        
        return issues
    
    async def enforce_rules(self, 
                           content: str, 
                           action_type: str,
                           series_id: int = None) -> Dict[str, Any]:
        """
        Check if an action violates established rules.
        
        Example: If "using this magic costs lifespan", 
        the system should track and warn about it.
        """
        # Get rules from knowledge base
        rules = await self._get_rules(series_id)
        
        if not rules or not self.llm_service:
            return {"violations": [], "warnings": []}
        
        rules_text = "\n".join([
            f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
            for r in rules[:10]
        ])
        
        prompt = f"""根據以下規則，檢查內容是否有違規：

【規則】
{rules_text}

【內容】
{content[:2000]}

【動作類型】
{action_type}

列出所有違規或需要觸發的後果（例如：使用禁咒需要消耗壽命）。
格式：每個問題一行，用 "- " 開頭。如果沒有違規，回答「符合規則」。"""

        try:
            response = await self.llm_service.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500
            )
            
            if "符合規則" in response:
                return {"violations": [], "warnings": []}
            
            issues = [line.strip("- ").strip() for line in response.split("\n") if line.strip().startswith("-")]
            return {"violations": issues, "warnings": []}
            
        except Exception as e:
            logger.error(f"Rule enforcement failed: {e}")
            return {"violations": [], "warnings": []}
    
    async def _get_worldbuilding_context(self, query: str, series_id: int) -> List[Dict]:
        """Get relevant worldbuilding from RAG."""
        if self.rag_service:
            context = await self.rag_service.retrieve_context(
                query=query[:500],
                include_chapters=False,
                series_id=series_id
            )
            return [k for k in context.get("knowledge", []) 
                    if k.get("category") in ["worldbuilding", "settings", "world_rule", "character"]]
        return []
    
    async def _get_rules(self, series_id: int) -> List[Dict]:
        """Get world rules from knowledge base."""
        if self.db:
            from sqlalchemy import text
            try:
                result = await self.db.execute(
                    text("""
                        SELECT title, content FROM knowledge_base 
                        WHERE category = 'world_rule' 
                        AND (tags @> :tag OR metadata->>'series_id' = :sid)
                        LIMIT 20
                    """),
                    {"tag": [f"series:{series_id}"], "sid": str(series_id)}
                )
                return [{"title": r.title, "content": r.content} for r in result.fetchall()]
            except:
                pass
        return []
    
    def _parse_consistency_response(self, response: str) -> List[ConsistencyIssue]:
        """Parse LLM response into ConsistencyIssue objects."""
        issues = []
        current_issue = {}
        
        for line in response.split("\n"):
            line = line.strip()
            if "問題類型:" in line or "類型:" in line:
                if current_issue.get("description"):
                    issues.append(ConsistencyIssue(
                        severity=current_issue.get("severity", "warning"),
                        category=current_issue.get("category", "worldbuilding"),
                        description=current_issue.get("description", ""),
                        source_reference=current_issue.get("source", ""),
                        suggestion=current_issue.get("suggestion", "")
                    ))
                current_issue = {"category": line.split(":")[-1].strip()}
            elif "嚴重程度:" in line:
                current_issue["severity"] = line.split(":")[-1].strip()
            elif "描述:" in line:
                current_issue["description"] = line.split(":")[-1].strip()
            elif "原設定出處:" in line or "出處:" in line:
                current_issue["source"] = line.split(":")[-1].strip()
            elif "建議修改:" in line or "建議:" in line:
                current_issue["suggestion"] = line.split(":")[-1].strip()
        
        # Don't forget the last one
        if current_issue.get("description"):
            issues.append(ConsistencyIssue(
                severity=current_issue.get("severity", "warning"),
                category=current_issue.get("category", "worldbuilding"),
                description=current_issue.get("description", ""),
                source_reference=current_issue.get("source", ""),
                suggestion=current_issue.get("suggestion", "")
            ))
        
        return issues


# ==================== Plot Strategist Agent ====================

class PlotStrategistAgent:
    """
    The master of plot architecture.
    
    Responsibilities:
    - Track foreshadowing and ensure payoffs
    - Analyze pacing (action vs dialogue balance)
    - Suggest plot developments
    - Maintain story arc coherence
    """
    
    def __init__(self, llm_service=None, db=None):
        self.llm_service = llm_service
        self.db = db
        self._plot_threads: Dict[str, PlotThread] = {}
    
    async def analyze_pacing(self, chapters: List[Dict]) -> Dict[str, Any]:
        """
        Analyze the pacing of recent chapters.
        
        Detects issues like "10 chapters of pure dialogue" or
        "no emotional beats in 5 chapters".
        """
        if not chapters or not self.llm_service:
            return {"analysis": "需要更多章節進行分析", "issues": [], "suggestions": []}
        
        chapters_text = "\n\n".join([
            f"第{ch.get('chapter_number', '?')}章：{ch.get('title', '')}\n{ch.get('content', '')[:1500]}..."
            for ch in chapters[:5]
        ])
        
        prompt = f"""分析以下章節的敘事節奏：

{chapters_text}

請評估：
1. 動作場面 vs 對話場面的比例
2. 情感高潮的分佈
3. 資訊揭露的密度
4. 讀者可能感到疲勞的地方

提供具體建議，指出哪裡需要加快/放慢節奏。"""

        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個小說節奏分析專家，專門優化長篇連載的可讀性。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            return {
                "analysis": response,
                "chapters_analyzed": len(chapters)
            }
            
        except Exception as e:
            logger.error(f"Pacing analysis failed: {e}")
            return {"analysis": "分析失敗", "error": str(e)}
    
    async def suggest_foreshadowing(self, 
                                    target_reveal: str, 
                                    current_chapter: int,
                                    reveal_chapter: int) -> List[str]:
        """
        Suggest where and how to plant foreshadowing.
        
        Example: If you want to reveal "Snape is good" in chapter 100,
        this suggests hints to plant in earlier chapters.
        """
        if not self.llm_service:
            return []
        
        chapters_until_reveal = reveal_chapter - current_chapter
        
        prompt = f"""我計劃在第 {reveal_chapter} 章揭露：「{target_reveal}」

目前寫到第 {current_chapter} 章，還有 {chapters_until_reveal} 章可以埋伏筆。

請建議 3-5 個伏筆，包括：
1. 建議在哪一章埋設
2. 伏筆的具體內容（要隱晦但回頭看能發現）
3. 為什麼這個伏筆有效

每個伏筆用「伏筆 N:」開頭。"""

        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個精通伏筆設計的小說大師，擅長「草蛇灰線」式的佈局。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            
            # Parse suggestions
            suggestions = []
            current = []
            for line in response.split("\n"):
                if line.strip().startswith("伏筆"):
                    if current:
                        suggestions.append("\n".join(current))
                    current = [line]
                elif current:
                    current.append(line)
            if current:
                suggestions.append("\n".join(current))
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Foreshadowing suggestion failed: {e}")
            return []
    
    async def check_unresolved_threads(self, series_id: int) -> List[Dict[str, Any]]:
        """
        Find plot threads that were planted but never resolved.
        
        The nightmare of every series writer: "Wait, what happened to that sword?"
        """
        if not self.db:
            return []
        
        from sqlalchemy import text
        
        try:
            # Get planted foreshadowing that's still open
            result = await self.db.execute(
                text("""
                    SELECT title, content, metadata 
                    FROM knowledge_base 
                    WHERE category = 'foreshadowing' 
                    AND (tags @> :tag OR metadata->>'series_id' = :sid)
                    AND (metadata->>'status' IS NULL OR metadata->>'status' != 'resolved')
                """),
                {"tag": [f"series:{series_id}"], "sid": str(series_id)}
            )
            
            threads = []
            for row in result.fetchall():
                metadata = json.loads(row.metadata) if row.metadata else {}
                threads.append({
                    "title": row.title,
                    "description": row.content[:200],
                    "planted_chapter": metadata.get("planted_chapter"),
                    "importance": metadata.get("importance", "unknown"),
                    "status": "unresolved"
                })
            
            return threads
            
        except Exception as e:
            logger.error(f"Failed to check unresolved threads: {e}")
            return []


# ==================== Character Director Agent ====================

class CharacterDirectorAgent:
    """
    The guardian of character authenticity.
    
    Responsibilities:
    - Maintain character voice consistency
    - Track relationship dynamics
    - Ensure emotional continuity
    - Generate dialogue that sounds like the character
    """
    
    def __init__(self, llm_service=None, db=None, rag_service=None):
        self.llm_service = llm_service
        self.db = db
        self.rag_service = rag_service
        self._character_states: Dict[str, CharacterState] = {}
    
    async def get_character_voice(self, 
                                  character_name: str, 
                                  series_id: int = None) -> Dict[str, Any]:
        """
        Get the speaking style and personality traits of a character.
        
        Returns info needed to write authentic dialogue.
        """
        voice_data = {
            "name": character_name,
            "speaking_style": "",
            "catchphrases": [],
            "personality_traits": [],
            "speech_patterns": [],
            "relationship_with": {}
        }
        
        if self.rag_service:
            context = await self.rag_service.retrieve_context(
                query=f"{character_name} 說話方式 性格 口頭禪",
                series_id=series_id
            )
            
            for item in context.get("knowledge", []):
                if character_name.lower() in item.get("title", "").lower() or \
                   character_name in item.get("content", ""):
                    content = item.get("content", "")
                    voice_data["speaking_style"] += content[:500]
        
        # Use LLM to extract specific traits
        if self.llm_service and voice_data["speaking_style"]:
            try:
                response = await self.llm_service.generate(
                    messages=[
                        {"role": "system", "content": "從角色描述中提取說話特徵。"},
                        {"role": "user", "content": f"""根據以下描述，提取 {character_name} 的說話特徵：

{voice_data['speaking_style']}

請列出：
1. 說話風格（例：刁鑽/木訥/優雅）
2. 口頭禪（如有）
3. 獨特的說話習慣
4. 情緒表達方式"""}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                voice_data["extracted_traits"] = response
            except:
                pass
        
        return voice_data
    
    async def check_dialogue_authenticity(self, 
                                         dialogue: str, 
                                         speaker: str,
                                         series_id: int = None) -> Dict[str, Any]:
        """
        Check if dialogue sounds like the character.
        
        Catches issues like: "Why is the stoic warrior suddenly making jokes?"
        """
        voice = await self.get_character_voice(speaker, series_id)
        
        if not self.llm_service:
            return {"authentic": True, "issues": []}
        
        prompt = f"""角色 {speaker} 的說話特徵：
{voice.get('speaking_style', '未知')[:500]}
{voice.get('extracted_traits', '')}

要檢查的對話：
「{dialogue}」

這段對話符合角色的說話風格嗎？
如果不符合，指出問題並建議修改。
如果符合，回答「符合角色」。"""

        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個角色對話審核專家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            if "符合角色" in response:
                return {"authentic": True, "issues": [], "analysis": response}
            
            return {"authentic": False, "issues": [response], "analysis": response}
            
        except Exception as e:
            logger.error(f"Dialogue check failed: {e}")
            return {"authentic": True, "issues": [], "error": str(e)}
    
    async def track_relationship_change(self,
                                       char_a: str,
                                       char_b: str,
                                       event: str,
                                       series_id: int = None):
        """
        Track when relationships change.
        
        If A and B fight, subsequent dialogue should be colder.
        """
        # This would update the graph database
        if self.db:
            from sqlalchemy import text
            try:
                await self.db.execute(
                    text("""
                        INSERT INTO knowledge_base 
                        (source_type, category, title, content, tags, metadata)
                        VALUES ('agent', 'relationship_event', :title, :content, :tags, :metadata)
                    """),
                    {
                        "title": f"{char_a} 與 {char_b} 關係變化",
                        "content": event,
                        "tags": [f"series:{series_id}", "relationship", char_a, char_b],
                        "metadata": json.dumps({
                            "series_id": series_id,
                            "characters": [char_a, char_b],
                            "event_type": "relationship_change",
                            "timestamp": datetime.now().isoformat()
                        })
                    }
                )
                await self.db.commit()
            except Exception as e:
                logger.error(f"Failed to track relationship: {e}")
    
    async def suggest_show_dont_tell(self, 
                                     telling_text: str) -> str:
        """
        Transform "telling" into "showing".
        
        Input: "He was angry"
        Output: "His fist slammed the table, sending tea cups rattling..."
        """
        if not self.llm_service:
            return telling_text
        
        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": """你是一個「展示而非講述」(Show Don't Tell) 專家。
將直接陳述的情緒或狀態，改寫成通過動作、表情、環境來展現。
使用具體的感官細節。"""},
                    {"role": "user", "content": f"請將以下「講述」改寫為「展示」：\n\n{telling_text}"}
                ],
                temperature=0.8,
                max_tokens=500
            )
            return response
        except:
            return telling_text


# ==================== Continuity Editor Agent ====================

class ContinuityEditorAgent:
    """
    The guardian against "eating the book" (吃書).
    
    Responsibilities:
    - Track where important objects are
    - Ensure dead characters stay dead
    - Validate timeline (pregnancy = 9 months, not 3)
    - Catch impossible situations
    """
    
    def __init__(self, llm_service=None, db=None, rag_service=None):
        self.llm_service = llm_service
        self.db = db
        self.rag_service = rag_service
        self._entity_states: Dict[str, EntityState] = {}
        self._character_states: Dict[str, CharacterState] = {}
    
    async def track_entity(self, 
                          entity_name: str, 
                          action: str, 
                          new_state: Dict[str, Any],
                          chapter: str,
                          series_id: int = None):
        """
        Track an important object or entity.
        
        Example: "倚天劍" is now held by "滅絕師太" as of "Chapter 5"
        """
        state = EntityState(
            name=entity_name,
            type=new_state.get("type", "object"),
            current_holder=new_state.get("holder"),
            location=new_state.get("location", "unknown"),
            status=new_state.get("status", "intact"),
            last_mentioned=chapter
        )
        
        self._entity_states[entity_name] = state
        
        # Persist to database
        if self.db:
            from sqlalchemy import text
            try:
                await self.db.execute(
                    text("""
                        INSERT INTO knowledge_base 
                        (source_type, category, title, content, tags, metadata)
                        VALUES ('continuity_agent', 'entity_state', :title, :content, :tags, :metadata)
                        ON CONFLICT (source_type, title) WHERE source_type = 'continuity_agent'
                        DO UPDATE SET content = :content, metadata = :metadata
                    """),
                    {
                        "title": f"實體狀態：{entity_name}",
                        "content": json.dumps({
                            "holder": state.current_holder,
                            "location": state.location,
                            "status": state.status,
                            "last_mentioned": state.last_mentioned
                        }, ensure_ascii=False),
                        "tags": [f"series:{series_id}", "entity_tracking", entity_name],
                        "metadata": json.dumps({
                            "series_id": series_id,
                            "entity_name": entity_name,
                            "last_update": datetime.now().isoformat()
                        })
                    }
                )
                await self.db.commit()
            except Exception as e:
                logger.error(f"Failed to track entity: {e}")
    
    async def check_entity_usage(self, 
                                content: str, 
                                series_id: int = None) -> List[Dict[str, Any]]:
        """
        Check if content uses entities correctly.
        
        Catches: "主角拔出倚天劍" when 倚天劍 is held by someone else.
        """
        issues = []
        
        # Get all tracked entities for this series
        entities = await self._get_tracked_entities(series_id)
        
        for entity in entities:
            entity_name = entity.get("name", "")
            if entity_name in content:
                # Check for conflicts
                current_holder = entity.get("holder")
                current_status = entity.get("status")
                
                # Simple pattern matching for common issues
                if current_status == "destroyed" and f"拿起{entity_name}" in content:
                    issues.append({
                        "entity": entity_name,
                        "issue": f"「{entity_name}」已被摧毀，無法拿起",
                        "last_state": entity
                    })
                
                if current_holder and f"從{current_holder}手中" not in content:
                    if any(action in content for action in [f"拔出{entity_name}", f"拿起{entity_name}", f"使用{entity_name}"]):
                        issues.append({
                            "entity": entity_name,
                            "issue": f"「{entity_name}」目前在{current_holder}手中",
                            "suggestion": f"需要先描述如何從{current_holder}處取得",
                            "last_state": entity
                        })
        
        return issues
    
    async def validate_timeline(self, 
                               events: List[Dict[str, Any]],
                               series_id: int = None) -> List[Dict[str, Any]]:
        """
        Validate that events make temporal sense.
        
        Catches: Character pregnant for 3 months then gives birth.
        """
        issues = []
        
        if not self.llm_service:
            return issues
        
        events_text = "\n".join([
            f"- {e.get('chapter', '?')}: {e.get('event', '')}"
            for e in events
        ])
        
        prompt = f"""檢查以下事件的時間線是否合理：

{events_text}

找出任何時間邏輯錯誤，例如：
- 懷孕到生產時間不對
- 旅程時間不合理
- 年齡計算錯誤
- 季節/天氣矛盾

如果沒有問題，回答「時間線正確」。"""

        try:
            response = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個時間線校對專家。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=800
            )
            
            if "時間線正確" not in response:
                issues.append({"type": "timeline", "description": response})
                
        except Exception as e:
            logger.error(f"Timeline validation failed: {e}")
        
        return issues
    
    async def check_character_state(self, 
                                   character: str, 
                                   action: str,
                                   series_id: int = None) -> Dict[str, Any]:
        """
        Check if a character can perform an action given their state.
        
        Catches: Dead character appearing, injured character fighting without recovery.
        """
        # Get character's last known state
        state = await self._get_character_state(character, series_id)
        
        if not state:
            return {"valid": True, "warnings": ["角色狀態未追蹤"]}
        
        warnings = []
        
        # Check for obvious issues
        if state.get("status") == "dead":
            return {"valid": False, "error": f"{character} 已死亡，無法執行任何動作"}
        
        if state.get("status") == "unconscious" and action not in ["醒來", "被救"]:
            warnings.append(f"{character} 上次出場時昏迷，需要描述如何恢復")
        
        if state.get("injuries") and any(injury in action for injury in ["戰鬥", "奔跑", "跳躍"]):
            warnings.append(f"{character} 有未痊癒的傷勢：{state.get('injuries')}")
        
        return {"valid": True, "warnings": warnings, "current_state": state}
    
    async def _get_tracked_entities(self, series_id: int) -> List[Dict]:
        """Get all tracked entities for a series."""
        if not self.db:
            return list(self._entity_states.values())
        
        from sqlalchemy import text
        try:
            result = await self.db.execute(
                text("""
                    SELECT title, content, metadata FROM knowledge_base
                    WHERE category = 'entity_state'
                    AND (tags @> :tag OR metadata->>'series_id' = :sid)
                """),
                {"tag": [f"series:{series_id}"], "sid": str(series_id)}
            )
            
            entities = []
            for row in result.fetchall():
                try:
                    content = json.loads(row.content)
                    content["name"] = row.title.replace("實體狀態：", "")
                    entities.append(content)
                except:
                    pass
            return entities
        except:
            return []
    
    async def _get_character_state(self, character: str, series_id: int) -> Optional[Dict]:
        """Get a character's last known state."""
        if character in self._character_states:
            state = self._character_states[character]
            return {
                "name": state.name,
                "location": state.location,
                "status": state.emotional_state,
                "injuries": state.injuries,
                "last_appearance": state.last_appearance
            }
        return None


# ==================== Main Orchestrator ====================

class NovelistAgentOrchestrator:
    """
    Orchestrates all agents for the novelist.
    
    This is the main interface that the Writing Assistant uses.
    """
    
    def __init__(self, llm_service=None, db=None, rag_service=None):
        self.world_architect = WorldArchitectAgent(llm_service, db, rag_service)
        self.plot_strategist = PlotStrategistAgent(llm_service, db)
        self.character_director = CharacterDirectorAgent(llm_service, db, rag_service)
        self.continuity_editor = ContinuityEditorAgent(llm_service, db, rag_service)
        
        self.llm_service = llm_service
        self.db = db
        self.rag_service = rag_service
    
    async def pre_write_check(self, 
                             writing_plan: str, 
                             series_id: int = None) -> Dict[str, Any]:
        """
        Check before writing: Are there any issues with the plan?
        
        Call this during the discussion phase.
        """
        results = {
            "consistency_warnings": [],
            "pacing_suggestions": [],
            "character_notes": [],
            "continuity_alerts": []
        }
        
        # Check worldbuilding consistency
        consistency_issues = await self.world_architect.check_consistency(writing_plan, series_id)
        results["consistency_warnings"] = [
            {"severity": i.severity, "description": i.description, "suggestion": i.suggestion}
            for i in consistency_issues
        ]
        
        # Check for unresolved plot threads
        unresolved = await self.plot_strategist.check_unresolved_threads(series_id)
        if unresolved:
            results["unresolved_threads"] = unresolved
        
        return results
    
    async def post_write_review(self, 
                               generated_content: str, 
                               series_id: int = None) -> Dict[str, Any]:
        """
        Review after writing: Does the content have issues?
        
        Call this after the AI generates a chapter.
        """
        results = {
            "consistency_issues": [],
            "entity_issues": [],
            "overall_quality": "pending"
        }
        
        # Full consistency check
        consistency_issues = await self.world_architect.check_consistency(generated_content, series_id)
        results["consistency_issues"] = [
            {
                "severity": i.severity,
                "category": i.category,
                "description": i.description,
                "source": i.source_reference,
                "suggestion": i.suggestion
            }
            for i in consistency_issues
        ]
        
        # Entity usage check
        entity_issues = await self.continuity_editor.check_entity_usage(generated_content, series_id)
        results["entity_issues"] = entity_issues
        
        # Determine overall quality
        critical_count = sum(1 for i in consistency_issues if i.severity == "critical")
        error_count = sum(1 for i in consistency_issues if i.severity == "error")
        
        if critical_count > 0:
            results["overall_quality"] = "needs_major_revision"
        elif error_count > 0:
            results["overall_quality"] = "needs_revision"
        elif len(consistency_issues) > 0:
            results["overall_quality"] = "acceptable_with_warnings"
        else:
            results["overall_quality"] = "good"
        
        return results
    
    async def get_writing_context(self, 
                                  chapter_plan: str, 
                                  characters: List[str],
                                  series_id: int = None) -> Dict[str, Any]:
        """
        Get all context needed for writing.
        
        Returns worldbuilding, character voices, and continuity state.
        """
        context = {
            "worldbuilding": [],
            "character_voices": {},
            "entity_states": [],
            "recent_events": []
        }
        
        # Get worldbuilding context
        if self.rag_service:
            rag_context = await self.rag_service.retrieve_context(
                query=chapter_plan,
                series_id=series_id
            )
            context["worldbuilding"] = rag_context.get("knowledge", [])[:15]
        
        # Get character voices
        for char in characters:
            voice = await self.character_director.get_character_voice(char, series_id)
            context["character_voices"][char] = voice
        
        # Get entity states
        context["entity_states"] = await self.continuity_editor._get_tracked_entities(series_id)
        
        return context


# Global instance
_orchestrator: Optional[NovelistAgentOrchestrator] = None


def get_novelist_orchestrator(llm_service=None, db=None, rag_service=None) -> NovelistAgentOrchestrator:
    """Get or create the orchestrator instance."""
    global _orchestrator
    
    if _orchestrator is None:
        _orchestrator = NovelistAgentOrchestrator(llm_service, db, rag_service)
    else:
        if llm_service:
            _orchestrator.llm_service = llm_service
            _orchestrator.world_architect.llm_service = llm_service
            _orchestrator.plot_strategist.llm_service = llm_service
            _orchestrator.character_director.llm_service = llm_service
            _orchestrator.continuity_editor.llm_service = llm_service
        if db:
            _orchestrator.db = db
        if rag_service:
            _orchestrator.rag_service = rag_service
    
    return _orchestrator
