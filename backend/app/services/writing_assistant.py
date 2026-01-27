"""
Writing Assistant - Conversational co-writer for novelists.

Simple flow:
1. Discuss → Chat about what you want in the chapter
2. Write → AI generates based on discussion + knowledge base
3. Refine → "Make it longer", "Add more dialogue", etc.

The assistant remembers your discussion and uses the knowledge base
to write chapters that match your worldbuilding.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class DiscussionMessage:
    """A message in the discussion."""
    role: str  # user or assistant
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class WritingSession:
    """A writing session for a chapter."""
    id: str
    series_id: Optional[int]
    book_id: Optional[int]
    chapter_number: Optional[int]
    chapter_title: Optional[str]
    
    # Discussion history
    discussion: List[DiscussionMessage] = field(default_factory=list)
    
    # What user wants (extracted from discussion)
    requirements: Dict[str, Any] = field(default_factory=dict)
    
    # Generated drafts (for iteration)
    drafts: List[str] = field(default_factory=list)
    current_draft: str = ""
    
    # Context from knowledge base
    worldbuilding_context: List[Dict] = field(default_factory=list)
    character_context: List[Dict] = field(default_factory=list)
    previous_chapters: List[Dict] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str):
        self.discussion.append(DiscussionMessage(role=role, content=content))
    
    def get_discussion_summary(self, max_messages: int = 10) -> str:
        """Get recent discussion as context."""
        recent = self.discussion[-max_messages:]
        return "\n".join([
            f"{'用戶' if m.role == 'user' else 'AI'}: {m.content}"
            for m in recent
        ])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "series_id": self.series_id,
            "book_id": self.book_id,
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "discussion": [m.to_dict() for m in self.discussion],
            "requirements": self.requirements,
            "draft_count": len(self.drafts),
            "has_current_draft": bool(self.current_draft),
            "created_at": self.created_at.isoformat()
        }


class WritingAssistant:
    """
    Your lazy novelist's best friend - powered by multi-agent system.
    
    Features:
    - World Architect: Catches consistency issues with worldbuilding
    - Plot Strategist: Manages foreshadowing and pacing
    - Character Director: Ensures authentic character voices
    - Continuity Editor: Tracks entities and timeline
    
    Usage:
    1. Start a session: assistant.start_session(series_id, ...)
    2. Discuss: assistant.discuss("I want chapter 3 to focus on...")
    3. Write: assistant.write_chapter()
    4. Refine: assistant.refine("Make the fight scene longer")
    5. Save: assistant.save_chapter()
    """
    
    def __init__(self, llm_service=None, rag_service=None, db=None):
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.db = db
        
        # Import and initialize the agent orchestrator
        from app.services.novelist_agents import get_novelist_orchestrator
        self.orchestrator = get_novelist_orchestrator(llm_service, db, rag_service)
        
        # Active sessions by ID
        self._sessions: Dict[str, WritingSession] = {}
    
    # ==================== Session Management ====================
    
    def start_session(self,
                     series_id: int = None,
                     book_id: int = None,
                     chapter_number: int = None,
                     chapter_title: str = None) -> WritingSession:
        """Start a new writing session."""
        import uuid
        session_id = str(uuid.uuid4())[:8]
        
        session = WritingSession(
            id=session_id,
            series_id=series_id,
            book_id=book_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title
        )
        
        self._sessions[session_id] = session
        logger.info(f"Started writing session {session_id}")
        
        return session
    
    def get_session(self, session_id: str) -> Optional[WritingSession]:
        """Get an existing session."""
        return self._sessions.get(session_id)
    
    def get_or_create_session(self, session_id: str = None, **kwargs) -> WritingSession:
        """Get existing session or create new one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.start_session(**kwargs)
    
    # ==================== Discussion Phase ====================
    
    async def discuss(self, 
                     session_id: str, 
                     user_message: str) -> str:
        """
        Chat about the chapter. The AI will:
        1. Understand what you want
        2. Ask clarifying questions
        3. Suggest ideas based on knowledge base
        4. Build up requirements for writing
        """
        session = self.get_session(session_id)
        if not session:
            return "找不到寫作會話，請先開始新會話。"
        
        # Add user message
        session.add_message("user", user_message)
        
        # Load context if not already loaded
        if not session.worldbuilding_context:
            await self._load_context(session)
        
        # Build discussion prompt
        context_summary = self._format_context_for_discussion(session)
        discussion_history = session.get_discussion_summary()
        
        # Detect intent
        is_write_request = self._is_write_request(user_message)
        
        if is_write_request:
            # User wants to write - extract requirements and confirm
            response = await self._prepare_for_writing(session, user_message)
        else:
            # Continue discussion
            response = await self._continue_discussion(session, user_message, context_summary, discussion_history)
        
        session.add_message("assistant", response)
        return response
    
    def _is_write_request(self, message: str) -> bool:
        """Check if user wants to start writing."""
        write_keywords = ['寫', '開始寫', '幫我寫', '動筆', '撰寫', 'write', 'start writing', 
                         '生成', '創作', '產生內容', '好了', '可以寫了', '開始吧']
        message_lower = message.lower()
        return any(kw in message_lower for kw in write_keywords)
    
    async def _continue_discussion(self, 
                                   session: WritingSession,
                                   user_message: str,
                                   context_summary: str,
                                   discussion_history: str) -> str:
        """Continue the discussion, ask questions, suggest ideas."""
        if not self.llm_service:
            return "LLM 服務不可用"
        
        # NOTE: Pre-write checks are disabled by default for speed
        # These add extra LLM calls that slow down discussion
        # Enable when needed for consistency checking
        agent_insights = ""
        # Pre-check is only enabled when user explicitly asks for consistency check
        # or when session has enable_consistency_check = True
        
        system_prompt = f"""你是一個專業的小說寫作助手。你正在和作者討論即將要寫的章節。

你的任務：
1. 理解作者想要什麼
2. 問清楚的問題（場景、角色、情緒、衝突等）
3. 根據世界觀提供建議
4. 幫助作者理清思路

世界觀資料：
{context_summary}

之前的討論：
{discussion_history}

注意：
- 用繁體中文回覆
- 簡潔但有建設性
- 主動提供創意建議
- 如果資訊足夠，問作者是否準備好開始寫
"""
        
        response = await self.llm_service.generate(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        # Extract any requirements mentioned
        self._extract_requirements(session, user_message)
        
        return response
    
    async def _prepare_for_writing(self, session: WritingSession, user_message: str) -> str:
        """Prepare to write - summarize what we'll write."""
        # Extract final requirements
        self._extract_requirements(session, user_message)
        
        # Generate a summary of what will be written
        discussion = session.get_discussion_summary()
        
        if self.llm_service:
            summary = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": """根據討論內容，整理出章節的寫作計畫。
格式：
**場景**: ...
**角色**: ...
**主要事件**: ...
**情緒基調**: ...
**重點**: ...

最後問：「這樣的方向可以嗎？如果沒問題，我就開始寫了。」"""},
                    {"role": "user", "content": f"討論內容：\n{discussion}"}
                ],
                temperature=0.5,
                max_tokens=500
            )
            return summary
        
        return "準備好了！說「開始」我就幫你寫。"
    
    def _extract_requirements(self, session: WritingSession, message: str):
        """Extract writing requirements from message."""
        # Simple keyword extraction
        message_lower = message.lower()
        
        if '角色' in message or '人物' in message:
            session.requirements['character_focus'] = True
        if '打鬥' in message or '戰鬥' in message:
            session.requirements['action'] = True
        if '對話' in message:
            session.requirements['dialogue_heavy'] = True
        if '長' in message or '詳細' in message:
            session.requirements['length'] = 'long'
        if '短' in message or '簡潔' in message:
            session.requirements['length'] = 'short'
    
    # ==================== Writing Phase ====================
    
    async def write_chapter(self, 
                           session_id: str,
                           additional_instructions: str = None) -> str:
        """
        Write the chapter based on discussion + knowledge base.
        This is the magic moment - AI writes while you relax.
        
        The multi-agent system will:
        1. Gather context from World Architect
        2. Get character voices from Character Director
        3. Generate the chapter
        4. Run post-write review for consistency
        """
        session = self.get_session(session_id)
        if not session:
            return "找不到寫作會話。"
        
        if not self.llm_service:
            return "LLM 服務不可用。"
        
        # Build the ultimate writing prompt
        prompt = self._build_writing_prompt(session, additional_instructions)
        
        logger.info(f"Writing chapter for session {session_id}")
        
        # Generate the chapter
        chapter_content = await self.llm_service.generate(
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]}
            ],
            temperature=0.8,
            max_tokens=3000
        )
        
        # NOTE: Post-write review is disabled by default for speed
        # Enable it when you want consistency checking (adds 30-60s to generation)
        # To enable: set session.requirements["enable_review"] = True
        if session.requirements.get("enable_review", False):
            try:
                review = await self.orchestrator.post_write_review(
                    chapter_content,
                    session.series_id
                )
                
                # If there are critical issues, add warnings to the draft
                if review.get("consistency_issues"):
                    issues = review["consistency_issues"]
                    critical_issues = [i for i in issues if i.get("severity") == "critical"]
                    
                    if critical_issues:
                        warning_text = "\n\n---\n⚠️ **一致性警告** (請在定稿前修正):\n"
                        for issue in critical_issues[:3]:
                            warning_text += f"- {issue.get('description', '')}\n"
                            if issue.get("suggestion"):
                                warning_text += f"  建議：{issue.get('suggestion')}\n"
                        chapter_content += warning_text
                
                # Store review results in session
                session.requirements["last_review"] = {
                    "quality": review.get("overall_quality"),
                    "issues_count": len(review.get("consistency_issues", [])),
                    "entity_issues": len(review.get("entity_issues", []))
                }
                
            except Exception as e:
                logger.warning(f"Post-write review failed: {e}")
        
        # Store the draft
        session.drafts.append(chapter_content)
        session.current_draft = chapter_content
        
        return chapter_content
    
    def _build_writing_prompt(self, session: WritingSession, additional: str = None) -> Dict[str, str]:
        """Build the prompt for chapter generation."""
        # Format worldbuilding context
        worldbuilding = "\n".join([
            f"【{item.get('title', '')}】\n{item.get('content', '')[:800]}"
            for item in session.worldbuilding_context[:10]
        ])
        
        # Format character context
        characters = "\n".join([
            f"【{item.get('title', '')}】\n{item.get('content', '')[:500]}"
            for item in session.character_context[:5]
        ])
        
        # Format previous chapters
        prev_chapters = ""
        if session.previous_chapters:
            prev_chapters = "\n\n".join([
                f"第{ch.get('chapter_number', '?')}章 {ch.get('title', '')}:\n{ch.get('content', '')[:1000]}..."
                for ch in session.previous_chapters[:2]
            ])
        
        # Get discussion summary
        discussion = session.get_discussion_summary(max_messages=15)
        
        # Build requirements string
        req_parts = []
        if session.requirements.get('length') == 'long':
            req_parts.append("篇幅要長，描寫要細膩")
        if session.requirements.get('action'):
            req_parts.append("包含精彩的動作/戰鬥場面")
        if session.requirements.get('dialogue_heavy'):
            req_parts.append("多用對話推進")
        requirements_str = "、".join(req_parts) if req_parts else "按正常標準撰寫"
        
        system_prompt = f"""你是一個專業的小說作家。現在要根據作者的討論和世界觀設定，撰寫一個章節。

【重要：嚴格遵循世界觀設定】
{worldbuilding}

【角色設定】
{characters}

【前情提要】
{prev_chapters if prev_chapters else "這是故事的開始"}

【與作者的討論】
{discussion}

【寫作要求】
{requirements_str}
{additional or ''}

【寫作指南】
1. **嚴格遵循世界觀** - 所有設定、名詞、規則必須與上述一致
2. **角色要立體** - 對話要符合角色性格
3. **場景要生動** - 用感官描寫讓讀者身臨其境
4. **節奏要把控** - 張弛有度，不要太趕或太拖
5. **留下懸念** - 章節結尾要吸引讀者繼續

直接開始寫章節內容，不要加任何前言或說明。"""

        chapter_info = ""
        if session.chapter_number:
            chapter_info = f"第{session.chapter_number}章"
        if session.chapter_title:
            chapter_info += f" {session.chapter_title}"
        
        user_prompt = f"請撰寫{chapter_info or '這一章'}的完整內容。"
        
        return {"system": system_prompt, "user": user_prompt}
    
    # ==================== Refine Phase ====================
    
    async def refine(self, 
                    session_id: str, 
                    instruction: str) -> str:
        """
        Refine the current draft.
        
        Examples:
        - "打鬥場面寫長一點"
        - "加入更多對話"
        - "結尾改成懸念"
        - "把主角的心理描寫加深"
        """
        session = self.get_session(session_id)
        if not session:
            return "找不到寫作會話。"
        
        if not session.current_draft:
            return "還沒有草稿可以修改。請先讓我寫一版。"
        
        if not self.llm_service:
            return "LLM 服務不可用。"
        
        # Add to discussion
        session.add_message("user", f"[修改要求] {instruction}")
        
        # Refine the draft
        refined = await self.llm_service.generate(
            messages=[
                {"role": "system", "content": f"""你是小說編輯。根據作者的要求修改以下章節。

修改要求：{instruction}

注意：
1. 保持原文的風格和基調
2. 只修改需要改的部分
3. 確保修改後的內容流暢自然
4. 輸出完整的修改後章節"""},
                {"role": "user", "content": f"原文：\n\n{session.current_draft}"}
            ],
            temperature=0.7,
            max_tokens=3000
        )
        
        # Store
        session.drafts.append(refined)
        session.current_draft = refined
        session.add_message("assistant", "[已完成修改]")
        
        return refined
    
    async def quick_refine(self, 
                          session_id: str, 
                          action: str) -> str:
        """
        Quick refinement actions.
        
        Actions:
        - "longer" - Make it longer
        - "shorter" - Make it shorter  
        - "more_dialogue" - Add more dialogue
        - "more_action" - Add more action
        - "more_emotion" - Deepen emotional content
        """
        action_map = {
            "longer": "把內容擴展得更長，增加更多細節描寫",
            "shorter": "精簡內容，保留精華",
            "more_dialogue": "增加更多對話，讓角色互動更豐富",
            "more_action": "加強動作場面的描寫",
            "more_emotion": "加深角色的心理和情感描寫",
        }
        
        instruction = action_map.get(action, action)
        return await self.refine(session_id, instruction)
    
    # ==================== Save Phase ====================
    
    async def save_chapter(self, 
                          session_id: str,
                          title: str = None) -> Dict[str, Any]:
        """Save the current draft as a chapter."""
        session = self.get_session(session_id)
        if not session or not session.current_draft:
            return {"success": False, "error": "沒有可保存的內容"}
        
        if not self.db:
            return {"success": False, "error": "資料庫不可用"}
        
        from sqlalchemy import text
        from app.services.embeddings import generate_embedding
        
        try:
            # Use provided title or session title
            final_title = title or session.chapter_title or f"第{session.chapter_number or '?'}章"
            
            # Generate embedding
            embedding = generate_embedding(f"{final_title}\n{session.current_draft[:2000]}")
            
            # Save to database
            result = await self.db.execute(
                text("""
                    INSERT INTO chapters (book_id, chapter_number, title, content, embedding, metadata)
                    VALUES (:book_id, :chapter_number, :title, :content, :embedding, :metadata)
                    ON CONFLICT (book_id, chapter_number) DO UPDATE SET
                        title = :title, content = :content, embedding = :embedding, updated_at = NOW()
                    RETURNING id
                """),
                {
                    "book_id": session.book_id,
                    "chapter_number": session.chapter_number or 1,
                    "title": final_title,
                    "content": session.current_draft,
                    "embedding": str(embedding),
                    "metadata": json.dumps({
                        "discussion_messages": len(session.discussion),
                        "draft_iterations": len(session.drafts),
                        "session_id": session.id
                    })
                }
            )
            await self.db.commit()
            chapter_id = result.scalar_one()
            
            return {
                "success": True,
                "chapter_id": chapter_id,
                "title": final_title,
                "word_count": len(session.current_draft)
            }
            
        except Exception as e:
            logger.error(f"Save chapter failed: {e}")
            await self.db.rollback()
            return {"success": False, "error": str(e)}
    
    # ==================== Context Loading ====================
    
    async def _load_context(self, session: WritingSession):
        """Load worldbuilding and character context for the session."""
        if not self.rag_service:
            return
        
        try:
            # Build query from session info
            query_parts = []
            if session.chapter_title:
                query_parts.append(session.chapter_title)
            query = " ".join(query_parts) if query_parts else "世界觀 設定 角色"
            
            # Get context from RAG
            context = await self.rag_service.retrieve_context(
                query=query,
                include_chapters=True,
                include_ideas=False,
                include_graph=False,
                series_id=session.series_id
            )
            
            # Separate by category
            for item in context.get("knowledge", []):
                category = item.get("category", "")
                if category in ["character", "faction"]:
                    session.character_context.append(item)
                else:
                    session.worldbuilding_context.append(item)
            
            # Get previous chapters
            if self.db and session.book_id:
                from sqlalchemy import text
                result = await self.db.execute(
                    text("""
                        SELECT chapter_number, title, content 
                        FROM chapters 
                        WHERE book_id = :book_id 
                        ORDER BY chapter_number DESC 
                        LIMIT 3
                    """),
                    {"book_id": session.book_id}
                )
                session.previous_chapters = [
                    {"chapter_number": r.chapter_number, "title": r.title, "content": r.content}
                    for r in result.fetchall()
                ]
            
            logger.info(f"Loaded context: {len(session.worldbuilding_context)} worldbuilding, "
                       f"{len(session.character_context)} characters, "
                       f"{len(session.previous_chapters)} previous chapters")
            
        except Exception as e:
            logger.error(f"Failed to load context: {e}")
    
    def _format_context_for_discussion(self, session: WritingSession) -> str:
        """Format context for discussion prompt."""
        parts = []
        
        if session.worldbuilding_context:
            parts.append("【世界觀重點】")
            for item in session.worldbuilding_context[:5]:
                parts.append(f"- {item.get('title', '')}: {item.get('content', '')[:200]}...")
        
        if session.character_context:
            parts.append("\n【主要角色】")
            for item in session.character_context[:3]:
                parts.append(f"- {item.get('title', '')}: {item.get('content', '')[:150]}...")
        
        return "\n".join(parts) if parts else "（暫無載入的世界觀資料）"


# Global instance
_writing_assistant: Optional[WritingAssistant] = None


def get_writing_assistant(llm_service=None, rag_service=None, db=None) -> WritingAssistant:
    """Get or create WritingAssistant instance."""
    global _writing_assistant
    
    if _writing_assistant is None:
        _writing_assistant = WritingAssistant(llm_service, rag_service, db)
    elif llm_service:
        _writing_assistant.llm_service = llm_service
    
    if rag_service:
        _writing_assistant.rag_service = rag_service
    if db:
        _writing_assistant.db = db
    
    return _writing_assistant
