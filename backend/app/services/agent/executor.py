"""
Task Executor - Executes individual tasks using available tools.

The executor runs tasks from the plan, manages tool invocation,
and handles errors gracefully.
"""
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime

from .planner import Task, TaskType, TaskStatus

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    Executes tasks using the agent's toolkit.
    
    Each task type maps to specific tool invocations and LLM calls.
    """
    
    def __init__(self, toolkit=None, llm_service=None, db=None):
        self.toolkit = toolkit
        self.llm_service = llm_service
        self.db = db
        self._execution_context = {}  # Shared context between tasks
    
    def set_context(self, key: str, value: Any):
        """Set a value in the shared execution context."""
        self._execution_context[key] = value
    
    def get_context(self, key: str, default=None) -> Any:
        """Get a value from the shared execution context."""
        return self._execution_context.get(key, default)
    
    async def execute(self, task: Task, plan_context: Dict[str, Any] = None) -> Task:
        """
        Execute a single task.
        
        Args:
            task: The task to execute
            plan_context: Context from the overall plan
        
        Returns:
            The task with updated status and result
        """
        task.status = TaskStatus.IN_PROGRESS
        logger.info(f"Executing task: {task.title} ({task.type.value})")
        
        try:
            # Merge contexts
            context = {**self._execution_context, **(plan_context or {})}
            
            # Execute based on task type
            result = await self._execute_by_type(task, context)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            
            # Store result in shared context for dependent tasks
            self.set_context(f"task_result_{task.id}", result)
            
            logger.info(f"Task completed: {task.title}")
            
        except Exception as e:
            logger.error(f"Task failed: {task.title} - {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        return task
    
    async def _execute_by_type(self, task: Task, context: Dict[str, Any]) -> Any:
        """Execute task based on its type."""
        
        handlers = {
            TaskType.RESEARCH_WORLDBUILDING: self._execute_research_worldbuilding,
            TaskType.RESEARCH_CHARACTERS: self._execute_research_characters,
            TaskType.RESEARCH_PLOT: self._execute_research_plot,
            TaskType.ANALYZE_CONSISTENCY: self._execute_analyze_consistency,
            TaskType.ANALYZE_PACING: self._execute_analyze_pacing,
            TaskType.WRITE_OUTLINE: self._execute_write_outline,
            TaskType.WRITE_CHAPTER: self._execute_write_chapter,
            TaskType.WRITE_SCENE: self._execute_write_scene,
            TaskType.WRITE_DIALOGUE: self._execute_write_dialogue,
            TaskType.REVIEW_CONTENT: self._execute_review_content,
            TaskType.IMPROVE_CONTENT: self._execute_improve_content,
            TaskType.FIX_INCONSISTENCY: self._execute_fix_inconsistency,
            TaskType.CREATE_CHARACTER: self._execute_create_character,
            TaskType.UPDATE_WORLDBUILDING: self._execute_update_worldbuilding,
            TaskType.TRACK_PLOT_THREAD: self._execute_track_plot_thread,
            TaskType.SUMMARIZE: self._execute_summarize,
            TaskType.WEB_SEARCH: self._execute_web_search,
            TaskType.USER_INPUT: self._execute_user_input,
        }
        
        handler = handlers.get(task.type)
        if not handler:
            raise ValueError(f"No handler for task type: {task.type}")
        
        return await handler(task, context)
    
    async def _execute_research_worldbuilding(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Research worldbuilding information using RAG."""
        query = task.parameters.get("query", "世界觀 設定")
        
        if self.toolkit:
            results = await self.toolkit.search_knowledge(
                query=query,
                categories=["worldbuilding", "settings", "world_rule"],
                limit=task.parameters.get("limit", 20)
            )
            return {
                "type": "worldbuilding_research",
                "query": query,
                "items": results,
                "count": len(results)
            }
        
        return {"type": "worldbuilding_research", "items": [], "count": 0}
    
    async def _execute_research_characters(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Research character information."""
        query = task.parameters.get("query", "角色 人物")
        
        if self.toolkit:
            results = await self.toolkit.search_knowledge(
                query=query,
                categories=["character", "faction"],
                limit=task.parameters.get("limit", 15)
            )
            
            # Also get character profiles from the graph
            profiles = await self.toolkit.get_character_profiles(query)
            
            return {
                "type": "character_research",
                "query": query,
                "knowledge_items": results,
                "character_profiles": profiles,
                "count": len(results) + len(profiles)
            }
        
        return {"type": "character_research", "knowledge_items": [], "character_profiles": [], "count": 0}
    
    async def _execute_research_plot(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Research plot and chapter information."""
        query = task.parameters.get("query", "情節 章節")
        
        if self.toolkit:
            # Search for plot-related knowledge
            knowledge = await self.toolkit.search_knowledge(
                query=query,
                categories=["plot", "chapter", "foreshadowing", "timeline"],
                limit=15
            )
            
            # Get recent chapters
            chapters = await self.toolkit.get_recent_chapters(
                series_id=context.get("series_id"),
                limit=5
            )
            
            return {
                "type": "plot_research",
                "query": query,
                "knowledge_items": knowledge,
                "chapters": chapters,
                "count": len(knowledge)
            }
        
        return {"type": "plot_research", "knowledge_items": [], "chapters": [], "count": 0}
    
    async def _execute_analyze_consistency(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Analyze content for consistency issues."""
        # Gather all research results
        worldbuilding = self.get_context("task_result_" + task.dependencies[0]) if task.dependencies else {}
        characters = self.get_context("task_result_" + task.dependencies[1]) if len(task.dependencies) > 1 else {}
        
        if self.llm_service:
            # Build analysis prompt
            prompt = self._build_consistency_prompt(worldbuilding, characters, task.parameters.get("content", ""))
            
            analysis = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個專業的小說一致性分析師。分析提供的內容，找出與世界觀設定或角色設定的矛盾。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            return {
                "type": "consistency_analysis",
                "analysis": analysis,
                "worldbuilding_items": len(worldbuilding.get("items", [])) if worldbuilding else 0,
                "character_items": len(characters.get("knowledge_items", [])) if characters else 0
            }
        
        return {"type": "consistency_analysis", "analysis": "分析功能需要 LLM 服務", "issues": []}
    
    async def _execute_analyze_pacing(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Analyze narrative pacing."""
        plot_research = self.get_context("task_result_" + task.dependencies[0]) if task.dependencies else {}
        
        if self.llm_service:
            chapters = plot_research.get("chapters", [])
            content = "\n\n".join([
                f"章節 {ch.get('chapter_number', '?')}: {ch.get('title', '')}\n{ch.get('content', '')[:2000]}"
                for ch in chapters
            ])
            
            analysis = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": """你是一個專業的敘事節奏分析師。分析提供的章節內容，評估：
1. 張力曲線 - 緊張感的起伏
2. 情緒節奏 - 情感的變化
3. 場景轉換 - 過渡的流暢度
4. 訊息密度 - 資訊的分佈
提供具體的改進建議。"""},
                    {"role": "user", "content": f"分析以下章節的敘事節奏：\n\n{content}"}
                ],
                temperature=0.5
            )
            
            return {
                "type": "pacing_analysis",
                "analysis": analysis,
                "chapters_analyzed": len(chapters)
            }
        
        return {"type": "pacing_analysis", "analysis": "分析功能需要 LLM 服務"}
    
    async def _execute_write_outline(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Write a content outline."""
        # Gather research results
        research_results = []
        for dep_id in task.dependencies:
            result = self.get_context(f"task_result_{dep_id}")
            if result:
                research_results.append(result)
        
        if self.llm_service:
            # Build context from research
            context_text = self._format_research_for_llm(research_results)
            
            outline = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": f"""你是一個專業的小說大綱撰寫者。
基於提供的世界觀和角色資訊，創建一個詳細的章節大綱。

大綱應包含：
1. 場景設定
2. 出場角色
3. 主要事件（3-5個關鍵點）
4. 情感走向
5. 結尾懸念/轉折

世界觀和角色資訊：
{context_text}"""},
                    {"role": "user", "content": f"目標：{task.parameters.get('goal', '撰寫大綱')}"}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return {
                "type": "outline",
                "content": outline,
                "goal": task.parameters.get("goal")
            }
        
        return {"type": "outline", "content": "需要 LLM 服務來生成大綱", "goal": task.parameters.get("goal")}
    
    async def _execute_write_chapter(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Write chapter content."""
        # Get outline if available
        outline = None
        for dep_id in task.dependencies:
            result = self.get_context(f"task_result_{dep_id}")
            if result and result.get("type") == "outline":
                outline = result.get("content")
                break
        
        # Get all research
        research_results = []
        for key, value in self._execution_context.items():
            if key.startswith("task_result_") and isinstance(value, dict):
                if value.get("type") in ["worldbuilding_research", "character_research", "plot_research"]:
                    research_results.append(value)
        
        if self.llm_service:
            context_text = self._format_research_for_llm(research_results)
            
            system_prompt = f"""你是一個專業的小說作家。根據提供的世界觀、角色資訊和大綱，撰寫生動的章節內容。

要求：
1. 嚴格遵循世界觀設定
2. 角色行為和對話要符合其性格
3. 場景描寫要生動具體
4. 保持敘事節奏的流暢

世界觀和角色資訊：
{context_text}"""
            
            if outline:
                system_prompt += f"\n\n章節大綱：\n{outline}"
            
            chapter_content = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"撰寫：{task.parameters.get('goal', '章節')}"}
                ],
                temperature=0.8,
                max_tokens=4000
            )
            
            return {
                "type": "chapter",
                "content": chapter_content,
                "goal": task.parameters.get("goal"),
                "has_outline": outline is not None
            }
        
        return {"type": "chapter", "content": "需要 LLM 服務來生成內容"}
    
    async def _execute_write_scene(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Write a scene."""
        research = self.get_context(f"task_result_{task.dependencies[0]}") if task.dependencies else {}
        
        if self.llm_service:
            context_text = self._format_research_for_llm([research]) if research else ""
            
            scene = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": f"""你是一個專業的場景撰寫者。創作生動、感官豐富的場景。

角色資訊：
{context_text}

要求：
1. 展示而非講述（Show, don't tell）
2. 運用五感描寫
3. 對話要自然且能反映角色性格
4. 控制場景節奏"""},
                    {"role": "user", "content": f"撰寫場景：{task.parameters.get('goal', '')}"}
                ],
                temperature=0.85,
                max_tokens=2000
            )
            
            return {"type": "scene", "content": scene}
        
        return {"type": "scene", "content": "需要 LLM 服務"}
    
    async def _execute_write_dialogue(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Write dialogue."""
        if self.llm_service:
            dialogue = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": """你是一個對話撰寫專家。創作自然、有特色的對話。

要求：
1. 每個角色有獨特的說話方式
2. 對話推動情節或揭示角色
3. 避免過於直白的說明性對話
4. 加入適當的動作和神態描寫"""},
                    {"role": "user", "content": f"撰寫對話：{task.parameters.get('goal', '')}"}
                ],
                temperature=0.8,
                max_tokens=1500
            )
            
            return {"type": "dialogue", "content": dialogue}
        
        return {"type": "dialogue", "content": "需要 LLM 服務"}
    
    async def _execute_review_content(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Review and critique content."""
        # Get content from previous task
        content_result = self.get_context(f"task_result_{task.dependencies[0]}") if task.dependencies else {}
        content = content_result.get("content", "")
        
        if self.llm_service and content:
            focus_areas = task.parameters.get("focus", ["quality", "consistency", "flow"])
            
            review = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": f"""你是一個專業的編輯和內容審查者。
對提供的內容進行批判性審查，重點關注：{', '.join(focus_areas)}

提供：
1. 整體評價（1-10分）
2. 具體問題清單
3. 改進建議
4. 優點亮點"""},
                    {"role": "user", "content": f"審查以下內容：\n\n{content[:6000]}"}
                ],
                temperature=0.4,
                max_tokens=2000
            )
            
            return {
                "type": "review",
                "review": review,
                "content_length": len(content),
                "focus_areas": focus_areas
            }
        
        return {"type": "review", "review": "沒有內容可審查"}
    
    async def _execute_improve_content(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Improve content based on review."""
        # Get original content and review
        original = None
        review = None
        
        for dep_id in task.dependencies:
            result = self.get_context(f"task_result_{dep_id}")
            if result:
                if result.get("type") == "review":
                    review = result.get("review")
                elif result.get("type") in ["chapter", "scene", "outline"]:
                    original = result.get("content")
        
        if self.llm_service and original:
            improved = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": f"""你是一個專業的內容改進專家。
根據審查意見改進內容，保持原有風格的同時解決指出的問題。

審查意見：
{review or '無具體審查意見，進行一般性改進'}"""},
                    {"role": "user", "content": f"改進以下內容：\n\n{original}"}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            return {
                "type": "improved_content",
                "content": improved,
                "original_length": len(original),
                "improved_length": len(improved)
            }
        
        return {"type": "improved_content", "content": original or "無內容可改進"}
    
    async def _execute_fix_inconsistency(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Fix consistency issues."""
        analysis = self.get_context(f"task_result_{task.dependencies[0]}") if task.dependencies else {}
        
        if self.llm_service:
            fixes = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個一致性修復專家。根據分析結果提供具體的修復方案。"},
                    {"role": "user", "content": f"根據以下分析提供修復方案：\n\n{analysis.get('analysis', '')}"}
                ],
                temperature=0.5
            )
            
            return {"type": "consistency_fix", "fixes": fixes}
        
        return {"type": "consistency_fix", "fixes": "需要 LLM 服務"}
    
    async def _execute_create_character(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Create a new character profile."""
        research = []
        for dep_id in task.dependencies:
            result = self.get_context(f"task_result_{dep_id}")
            if result:
                research.append(result)
        
        if self.llm_service:
            context_text = self._format_research_for_llm(research)
            
            character = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": f"""你是一個角色設計專家。創建詳細的角色檔案。

世界觀背景：
{context_text}

角色檔案應包含：
1. 基本資訊（姓名、年齡、外貌）
2. 背景故事
3. 性格特點（包括缺點）
4. 動機與目標
5. 說話方式和習慣
6. 與其他角色的關係
7. 在故事中的角色定位"""},
                    {"role": "user", "content": f"創建角色：{task.parameters.get('goal', '')}"}
                ],
                temperature=0.8,
                max_tokens=2000
            )
            
            return {"type": "character", "profile": character}
        
        return {"type": "character", "profile": "需要 LLM 服務"}
    
    async def _execute_update_worldbuilding(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Update worldbuilding settings."""
        research = self.get_context(f"task_result_{task.dependencies[0]}") if task.dependencies else {}
        
        if self.llm_service:
            existing = "\n".join([
                f"- {item.get('title', '')}: {item.get('content', '')[:200]}"
                for item in research.get("items", [])
            ])
            
            update = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": f"""你是一個世界觀設計專家。更新或添加世界觀設定。

現有設定：
{existing}

要求：
1. 與現有設定保持一致
2. 提供具體細節
3. 考慮邏輯合理性"""},
                    {"role": "user", "content": f"更新設定：{task.parameters.get('goal', '')}"}
                ],
                temperature=0.7
            )
            
            return {"type": "worldbuilding_update", "content": update}
        
        return {"type": "worldbuilding_update", "content": "需要 LLM 服務"}
    
    async def _execute_track_plot_thread(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Track and manage plot threads."""
        if self.toolkit:
            threads = await self.toolkit.get_plot_threads(context.get("series_id"))
            return {"type": "plot_threads", "threads": threads}
        
        return {"type": "plot_threads", "threads": []}
    
    async def _execute_summarize(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Summarize results from previous tasks."""
        results = []
        for dep_id in task.dependencies:
            result = self.get_context(f"task_result_{dep_id}")
            if result:
                results.append(result)
        
        if self.llm_service and results:
            content = "\n\n".join([
                f"【{r.get('type', 'unknown')}】\n{str(r)[:1000]}"
                for r in results
            ])
            
            summary = await self.llm_service.generate(
                messages=[
                    {"role": "system", "content": "你是一個專業的總結撰寫者。將複雜的分析結果整理成清晰的報告。"},
                    {"role": "user", "content": f"總結以下內容：\n\n{content}"}
                ],
                temperature=0.5,
                max_tokens=1500
            )
            
            return {"type": "summary", "content": summary, "sources": len(results)}
        
        return {"type": "summary", "content": "無內容可總結"}
    
    async def _execute_web_search(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Execute web search."""
        if self.toolkit:
            results = await self.toolkit.web_search(
                task.parameters.get("query", ""),
                max_results=task.parameters.get("limit", 5)
            )
            return {"type": "web_search", "results": results}
        
        return {"type": "web_search", "results": []}
    
    async def _execute_user_input(self, task: Task, context: Dict) -> Dict[str, Any]:
        """Wait for user input (handled externally)."""
        task.status = TaskStatus.NEEDS_USER_INPUT
        return {"type": "user_input", "prompt": task.parameters.get("prompt", "需要您的輸入")}
    
    def _build_consistency_prompt(self, worldbuilding: Dict, characters: Dict, content: str) -> str:
        """Build prompt for consistency analysis."""
        parts = []
        
        if worldbuilding and worldbuilding.get("items"):
            parts.append("世界觀設定：")
            for item in worldbuilding["items"][:10]:
                parts.append(f"- {item.get('title', '')}: {item.get('content', '')[:300]}")
        
        if characters:
            if characters.get("knowledge_items"):
                parts.append("\n角色設定：")
                for item in characters["knowledge_items"][:10]:
                    parts.append(f"- {item.get('title', '')}: {item.get('content', '')[:300]}")
        
        parts.append(f"\n要分析的內容：\n{content[:3000]}")
        
        return "\n".join(parts)
    
    def _format_research_for_llm(self, research_results: List[Dict]) -> str:
        """Format research results into context for LLM."""
        parts = []
        
        for research in research_results:
            if not research:
                continue
                
            research_type = research.get("type", "unknown")
            
            if research_type == "worldbuilding_research":
                parts.append("【世界觀設定】")
                for item in research.get("items", [])[:15]:
                    parts.append(f"- {item.get('title', '')}:\n  {item.get('content', '')[:500]}")
            
            elif research_type == "character_research":
                parts.append("\n【角色資訊】")
                for item in research.get("knowledge_items", [])[:10]:
                    parts.append(f"- {item.get('title', '')}:\n  {item.get('content', '')[:400]}")
                for profile in research.get("character_profiles", [])[:5]:
                    parts.append(f"- {profile.get('name', '')}:\n  {profile.get('description', '')[:300]}")
            
            elif research_type == "plot_research":
                parts.append("\n【情節資訊】")
                for item in research.get("knowledge_items", [])[:10]:
                    parts.append(f"- {item.get('title', '')}:\n  {item.get('content', '')[:400]}")
                if research.get("chapters"):
                    parts.append("\n最近章節：")
                    for ch in research.get("chapters", [])[:3]:
                        parts.append(f"- 第{ch.get('chapter_number', '?')}章：{ch.get('title', '')}")
        
        return "\n".join(parts)
