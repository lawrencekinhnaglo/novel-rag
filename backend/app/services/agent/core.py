"""
NovelAgent - The core agentic AI for novelists.

This is the main agent that orchestrates:
- Task planning and decomposition
- Autonomous task execution
- Self-review and iteration
- Learning from feedback
- Proactive monitoring
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging
import uuid

from .planner import TaskPlanner, TaskPlan, Task, TaskStatus
from .executor import TaskExecutor
from .memory import AgentMemory, PlotThread
from .critic import SelfCritic, CritiqueResult
from .tools import AgentToolkit

logger = logging.getLogger(__name__)

# Global agent instance
_novel_agent: Optional['NovelAgent'] = None


@dataclass
class AgentResponse:
    """Response from the agent after working on a goal."""
    success: bool
    plan_id: str
    goal: str
    final_output: str
    tasks_completed: int
    tasks_failed: int
    iterations: int
    critique_score: float
    duration_seconds: float
    artifacts: Dict[str, Any]  # Generated content, knowledge items, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "plan_id": self.plan_id,
            "goal": self.goal,
            "final_output": self.final_output,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "iterations": self.iterations,
            "critique_score": self.critique_score,
            "duration_seconds": self.duration_seconds,
            "artifacts": self.artifacts
        }


class NovelAgent:
    """
    The main agentic AI for novelists.
    
    Capabilities:
    - Goal → Plan → Execute → Review → Iterate workflow
    - Autonomous task execution with multiple tools
    - Self-criticism and quality control
    - Learning from user feedback
    - Proactive story monitoring
    """
    
    def __init__(self, 
                 llm_service=None, 
                 rag_service=None, 
                 db=None,
                 user_id: str = None,
                 series_id: int = None,
                 max_iterations: int = 3,
                 min_quality_score: float = 7.0):
        """
        Initialize the agent.
        
        Args:
            llm_service: LLM service for generation
            rag_service: RAG service for context retrieval
            db: Database session
            user_id: User identifier for personalization
            series_id: Default series context
            max_iterations: Maximum improvement iterations
            min_quality_score: Minimum score to consider output satisfactory
        """
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.db = db
        self.user_id = user_id
        self.series_id = series_id
        self.max_iterations = max_iterations
        self.min_quality_score = min_quality_score
        
        # Initialize components
        self.planner = TaskPlanner(llm_service)
        self.toolkit = AgentToolkit(db, rag_service, llm_service)
        self.executor = TaskExecutor(self.toolkit, llm_service, db)
        self.memory = AgentMemory(db, user_id, series_id)
        self.critic = SelfCritic(llm_service, min_quality_score)
        
        # State
        self._current_plan: Optional[TaskPlan] = None
        self._is_working = False
    
    async def initialize(self):
        """Initialize the agent and load memory."""
        await self.memory.load_from_database()
        logger.info(f"Agent initialized with memory: {self.memory.get_summary()}")
    
    # ==================== Main Workflow ====================
    
    async def work_on_goal(self, goal: str, context: Dict[str, Any] = None) -> AgentResponse:
        """
        Main entry point: Work autonomously to achieve a goal.
        
        Args:
            goal: The user's goal (e.g., "Write chapter 3 of Book 1")
            context: Additional context (series_id, book_id, etc.)
        
        Returns:
            AgentResponse with results
        """
        start_time = datetime.now()
        self._is_working = True
        
        logger.info(f"Agent starting work on goal: {goal}")
        
        try:
            # Merge context
            full_context = {
                "series_id": self.series_id,
                "user_id": self.user_id,
                **(context or {})
            }
            
            # Step 1: Plan
            plan = await self.planner.plan(goal, full_context)
            self._current_plan = plan
            logger.info(f"Created plan with {len(plan.tasks)} tasks")
            
            # Step 2: Execute with iteration
            iterations = 0
            final_output = ""
            critique_result = None
            
            while iterations < self.max_iterations:
                iterations += 1
                logger.info(f"Iteration {iterations}/{self.max_iterations}")
                
                # Execute all tasks
                await self._execute_plan(plan, full_context)
                
                # Get final output from the plan
                final_output = self._extract_final_output(plan)
                
                # Step 3: Self-critique
                if final_output:
                    worldbuilding = await self.toolkit.search_knowledge(
                        goal, categories=["worldbuilding", "settings"], limit=10
                    )
                    
                    critique_result = await self.critic.review(
                        content=final_output,
                        content_type=self._get_content_type(goal),
                        context={"worldbuilding": worldbuilding}
                    )
                    
                    logger.info(f"Critique score: {critique_result.score}")
                    
                    # If satisfactory, we're done
                    if critique_result.satisfactory:
                        logger.info("Output is satisfactory")
                        break
                    
                    # Otherwise, try to improve
                    if iterations < self.max_iterations:
                        logger.info("Output needs improvement, iterating...")
                        final_output = await self._improve_output(
                            final_output, 
                            critique_result,
                            full_context
                        )
                else:
                    break
            
            # Calculate results
            progress = plan.get_progress()
            duration = (datetime.now() - start_time).total_seconds()
            
            # Store in memory
            await self.memory.store(
                memory_type="completed_goal",
                content={
                    "goal": goal,
                    "success": progress["failed"] == 0,
                    "iterations": iterations,
                    "score": critique_result.score if critique_result else 0
                },
                importance=0.7
            )
            
            return AgentResponse(
                success=progress["failed"] == 0,
                plan_id=plan.id,
                goal=goal,
                final_output=final_output,
                tasks_completed=progress["completed"],
                tasks_failed=progress["failed"],
                iterations=iterations,
                critique_score=critique_result.score if critique_result else 0,
                duration_seconds=duration,
                artifacts=self._collect_artifacts(plan)
            )
            
        except Exception as e:
            logger.error(f"Agent error: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            
            return AgentResponse(
                success=False,
                plan_id=self._current_plan.id if self._current_plan else "error",
                goal=goal,
                final_output=f"執行過程中發生錯誤：{str(e)}",
                tasks_completed=0,
                tasks_failed=1,
                iterations=0,
                critique_score=0,
                duration_seconds=duration,
                artifacts={}
            )
        
        finally:
            self._is_working = False
    
    async def work_on_goal_stream(self, 
                                  goal: str, 
                                  context: Dict[str, Any] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream progress updates while working on a goal.
        
        Yields progress updates as the agent works.
        """
        self._is_working = True
        
        yield {"type": "start", "goal": goal, "timestamp": datetime.now().isoformat()}
        
        try:
            # Plan
            yield {"type": "planning", "message": "正在規劃任務..."}
            
            full_context = {"series_id": self.series_id, **(context or {})}
            plan = await self.planner.plan(goal, full_context)
            self._current_plan = plan
            
            yield {
                "type": "plan_created",
                "plan_id": plan.id,
                "tasks": [t.to_dict() for t in plan.tasks]
            }
            
            # Execute tasks
            iterations = 0
            while iterations < self.max_iterations:
                iterations += 1
                
                yield {"type": "iteration_start", "iteration": iterations}
                
                # Execute each task
                while True:
                    task = plan.get_next_task()
                    if not task:
                        break
                    
                    yield {
                        "type": "task_start",
                        "task_id": task.id,
                        "task_title": task.title,
                        "task_type": task.type.value
                    }
                    
                    await self.executor.execute(task, full_context)
                    
                    yield {
                        "type": "task_complete",
                        "task_id": task.id,
                        "status": task.status.value,
                        "result_type": task.result.get("type") if task.result else None
                    }
                
                # Critique
                final_output = self._extract_final_output(plan)
                if final_output:
                    yield {"type": "reviewing", "message": "正在審查內容..."}
                    
                    critique = await self.critic.review(
                        final_output, 
                        self._get_content_type(goal)
                    )
                    
                    yield {
                        "type": "critique",
                        "score": critique.score,
                        "satisfactory": critique.satisfactory,
                        "summary": critique.summary[:200]
                    }
                    
                    if critique.satisfactory:
                        break
                    
                    if iterations < self.max_iterations:
                        yield {"type": "improving", "message": "正在改進內容..."}
                        final_output = await self._improve_output(
                            final_output, critique, full_context
                        )
                else:
                    break
            
            # Final result
            progress = plan.get_progress()
            
            yield {
                "type": "complete",
                "success": progress["failed"] == 0,
                "tasks_completed": progress["completed"],
                "tasks_failed": progress["failed"],
                "iterations": iterations,
                "final_output": final_output[:500] if final_output else ""
            }
            
        except Exception as e:
            yield {"type": "error", "message": str(e)}
        
        finally:
            self._is_working = False
    
    async def _execute_plan(self, plan: TaskPlan, context: Dict[str, Any]):
        """Execute all tasks in a plan."""
        while True:
            task = plan.get_next_task()
            if not task:
                break
            
            await self.executor.execute(task, context)
            
            # Handle tasks that need user input
            if task.status == TaskStatus.NEEDS_USER_INPUT:
                logger.info(f"Task {task.id} needs user input")
                # In a real implementation, we'd wait for user input
                # For now, skip and continue
                task.status = TaskStatus.COMPLETED
    
    async def _improve_output(self, 
                             output: str, 
                             critique: CritiqueResult,
                             context: Dict[str, Any]) -> str:
        """Improve output based on critique."""
        if not self.llm_service:
            return output
        
        issues = "\n".join([
            f"- [{item.severity}] {item.issue}"
            for item in critique.items[:5]
        ])
        
        recommendations = "\n".join([f"- {r}" for r in critique.recommendations])
        
        improved = await self.llm_service.generate(
            messages=[
                {"role": "system", "content": f"""你是一個專業的內容改進專家。
根據審查意見改進內容，解決指出的問題，同時保持原有風格和優點。

發現的問題：
{issues}

建議：
{recommendations}"""},
                {"role": "user", "content": f"請改進以下內容：\n\n{output}"}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        return improved
    
    def _extract_final_output(self, plan: TaskPlan) -> str:
        """Extract the final output from a completed plan."""
        # Look for content in completed tasks (prefer improved > original)
        for task in reversed(plan.tasks):
            if task.status == TaskStatus.COMPLETED and task.result:
                result = task.result
                if result.get("type") in ["improved_content", "chapter", "scene", "outline"]:
                    return result.get("content", "")
        
        return ""
    
    def _collect_artifacts(self, plan: TaskPlan) -> Dict[str, Any]:
        """Collect all artifacts from a completed plan."""
        artifacts = {}
        
        for task in plan.tasks:
            if task.status == TaskStatus.COMPLETED and task.result:
                result_type = task.result.get("type", "unknown")
                
                if result_type not in artifacts:
                    artifacts[result_type] = []
                
                artifacts[result_type].append({
                    "task_id": task.id,
                    "content": task.result
                })
        
        return artifacts
    
    def _get_content_type(self, goal: str) -> str:
        """Determine content type from goal."""
        goal_lower = goal.lower()
        
        if any(kw in goal_lower for kw in ['章', 'chapter']):
            return "chapter"
        elif any(kw in goal_lower for kw in ['場景', 'scene']):
            return "scene"
        elif any(kw in goal_lower for kw in ['大綱', 'outline']):
            return "outline"
        elif any(kw in goal_lower for kw in ['角色', 'character']):
            return "character"
        
        return "content"
    
    # ==================== Proactive Features ====================
    
    async def check_consistency(self, 
                               content: str = None, 
                               chapter_id: int = None) -> Dict[str, Any]:
        """
        Proactively check content for consistency issues.
        
        Args:
            content: Content to check (or fetch from chapter_id)
            chapter_id: Chapter to check
        
        Returns:
            Dict with consistency analysis
        """
        if chapter_id and not content:
            chapter = await self.toolkit.get_chapter(chapter_id)
            if chapter:
                content = chapter.get("content", "")
        
        if not content:
            return {"error": "No content to check"}
        
        # Get worldbuilding for comparison
        worldbuilding = await self.toolkit.search_knowledge(
            content[:500],  # Use first part as query
            categories=["worldbuilding", "settings", "character"],
            limit=15
        )
        
        result = await self.critic.quick_check(content, worldbuilding)
        
        return {
            "consistent": result["consistent"],
            "issues": result["issues"],
            "worldbuilding_checked": len(worldbuilding)
        }
    
    async def get_forgotten_threads(self, current_chapter: int = 0) -> List[Dict[str, Any]]:
        """Get plot threads that might have been forgotten."""
        threads = await self.memory.get_forgotten_threads(
            chapters_since=5,
            current_chapter=current_chapter
        )
        
        return [t.to_dict() for t in threads]
    
    async def suggest_next_steps(self, context: Dict[str, Any] = None) -> List[str]:
        """
        Suggest next steps for the author.
        Based on open plot threads, pacing, and story progress.
        """
        suggestions = []
        
        # Check for open plot threads
        open_threads = await self.memory.get_open_plot_threads()
        if open_threads:
            high_priority = [t for t in open_threads if t.importance in ["high", "critical"]]
            if high_priority:
                suggestions.append(f"有 {len(high_priority)} 個重要情節線尚未解決")
        
        # Get learned preferences
        if context and context.get("last_task_type"):
            prefs = await self.memory.get_learned_preferences(context["last_task_type"])
            if prefs.get("feedback_stats"):
                stats = prefs["feedback_stats"]
                if stats.get("negative", 0) > stats.get("positive", 0):
                    suggestions.append("根據反饋，您可能需要調整最近的寫作方向")
        
        # Default suggestions
        if not suggestions:
            suggestions.extend([
                "繼續撰寫下一章",
                "檢查故事一致性",
                "發展角色關係"
            ])
        
        return suggestions[:5]
    
    # ==================== Feedback Learning ====================
    
    async def record_feedback(self, 
                             task_type: str,
                             content: str,
                             feedback: str,
                             details: Dict[str, Any] = None):
        """Record user feedback for learning."""
        await self.memory.record_feedback(task_type, content, feedback, details)
    
    # ==================== State ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "is_working": self._is_working,
            "current_plan": self._current_plan.to_dict() if self._current_plan else None,
            "memory_summary": self.memory.get_summary()
        }
    
    def get_current_progress(self) -> Optional[Dict[str, Any]]:
        """Get progress of current work."""
        if self._current_plan:
            return self._current_plan.get_progress()
        return None


def get_novel_agent(llm_service=None, 
                    rag_service=None, 
                    db=None,
                    user_id: str = None,
                    series_id: int = None) -> NovelAgent:
    """Get or create a NovelAgent instance."""
    global _novel_agent
    
    if _novel_agent is None:
        _novel_agent = NovelAgent(
            llm_service=llm_service,
            rag_service=rag_service,
            db=db,
            user_id=user_id,
            series_id=series_id
        )
    
    return _novel_agent
