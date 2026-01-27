"""
Task Planner - Decomposes goals into executable tasks.

The planner analyzes user goals and creates a structured plan
of tasks that can be executed by the agent.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of tasks the agent can perform."""
    # Research & Analysis
    RESEARCH_WORLDBUILDING = "research_worldbuilding"
    RESEARCH_CHARACTERS = "research_characters"
    RESEARCH_PLOT = "research_plot"
    ANALYZE_CONSISTENCY = "analyze_consistency"
    ANALYZE_PACING = "analyze_pacing"
    
    # Content Generation
    WRITE_OUTLINE = "write_outline"
    WRITE_CHAPTER = "write_chapter"
    WRITE_SCENE = "write_scene"
    WRITE_DIALOGUE = "write_dialogue"
    
    # Content Improvement
    REVIEW_CONTENT = "review_content"
    IMPROVE_CONTENT = "improve_content"
    FIX_INCONSISTENCY = "fix_inconsistency"
    
    # Knowledge Management
    CREATE_CHARACTER = "create_character"
    UPDATE_WORLDBUILDING = "update_worldbuilding"
    TRACK_PLOT_THREAD = "track_plot_thread"
    
    # Utility
    SUMMARIZE = "summarize"
    WEB_SEARCH = "web_search"
    USER_INPUT = "user_input"  # Requires user approval/input


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Waiting for dependencies
    NEEDS_USER_INPUT = "needs_user_input"


@dataclass
class Task:
    """A single task in the agent's plan."""
    id: str
    type: TaskType
    title: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # IDs of tasks this depends on
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    estimated_tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "description": self.description,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "estimated_tokens": self.estimated_tokens
        }


@dataclass
class TaskPlan:
    """A complete plan with multiple tasks."""
    id: str
    goal: str
    tasks: List[Task] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next executable task (all dependencies completed)."""
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                # Check if all dependencies are completed
                deps_completed = all(
                    self.get_task(dep_id).status == TaskStatus.COMPLETED
                    for dep_id in task.dependencies
                    if self.get_task(dep_id)
                )
                if deps_completed:
                    return task
        return None
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        return all(t.status == TaskStatus.COMPLETED for t in self.tasks)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get progress summary."""
        total = len(self.tasks)
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        in_progress = sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": total - completed - failed - in_progress,
            "percent": (completed / total * 100) if total > 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks],
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "progress": self.get_progress()
        }


class TaskPlanner:
    """
    Plans and decomposes goals into executable tasks.
    
    Uses LLM to understand goals and create appropriate task sequences.
    """
    
    def __init__(self, llm_service=None):
        self.llm_service = llm_service
        self._task_counter = 0
    
    def _generate_task_id(self) -> str:
        self._task_counter += 1
        return f"task_{self._task_counter}_{datetime.now().strftime('%H%M%S')}"
    
    async def plan(self, goal: str, context: Dict[str, Any] = None) -> TaskPlan:
        """
        Create a plan to achieve the given goal.
        
        Args:
            goal: The user's goal (e.g., "Write chapter 3 of Book 1")
            context: Additional context (series_id, current progress, etc.)
        
        Returns:
            A TaskPlan with ordered tasks
        """
        import uuid
        plan_id = str(uuid.uuid4())[:8]
        
        # Analyze the goal to determine task type
        goal_lower = goal.lower()
        
        # Detect goal type and create appropriate plan
        if any(kw in goal_lower for kw in ['寫', 'write', '撰寫', '創作']):
            if any(kw in goal_lower for kw in ['章', 'chapter']):
                return await self._plan_write_chapter(plan_id, goal, context)
            elif any(kw in goal_lower for kw in ['大綱', 'outline', '概要']):
                return await self._plan_write_outline(plan_id, goal, context)
            elif any(kw in goal_lower for kw in ['場景', 'scene']):
                return await self._plan_write_scene(plan_id, goal, context)
            else:
                return await self._plan_write_content(plan_id, goal, context)
        
        elif any(kw in goal_lower for kw in ['檢查', 'check', '分析', 'analyze', '審查', 'review']):
            if any(kw in goal_lower for kw in ['一致', 'consistency', '矛盾', 'contradiction']):
                return await self._plan_consistency_check(plan_id, goal, context)
            elif any(kw in goal_lower for kw in ['節奏', 'pacing', '張力', 'tension']):
                return await self._plan_pacing_analysis(plan_id, goal, context)
            else:
                return await self._plan_general_analysis(plan_id, goal, context)
        
        elif any(kw in goal_lower for kw in ['創建', 'create', '建立', '新增', 'add']):
            if any(kw in goal_lower for kw in ['角色', 'character', '人物']):
                return await self._plan_create_character(plan_id, goal, context)
            elif any(kw in goal_lower for kw in ['世界', 'world', '設定', 'setting']):
                return await self._plan_update_worldbuilding(plan_id, goal, context)
        
        elif any(kw in goal_lower for kw in ['改進', 'improve', '優化', '修改', 'revise', 'edit']):
            return await self._plan_improve_content(plan_id, goal, context)
        
        # Default: Use LLM to determine plan
        return await self._plan_with_llm(plan_id, goal, context)
    
    async def _plan_write_chapter(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for writing a chapter."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="研究世界觀設定",
                description="檢索相關的世界觀、設定和規則",
                parameters={"query": goal, "focus": "worldbuilding"}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_CHARACTERS,
                title="分析相關角色",
                description="找出本章相關角色的性格、動機和說話方式",
                parameters={"query": goal, "focus": "characters"},
                dependencies=[]
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_PLOT,
                title="檢查情節連貫性",
                description="回顧之前章節，確保情節連貫",
                parameters={"query": goal, "focus": "plot_continuity"},
                dependencies=[]
            ),
        ]
        
        # Add dependency for outline task
        research_ids = [t.id for t in tasks]
        
        tasks.append(Task(
            id=self._generate_task_id(),
            type=TaskType.WRITE_OUTLINE,
            title="撰寫章節大綱",
            description="基於研究結果，創建章節的詳細大綱",
            parameters={"goal": goal},
            dependencies=research_ids,
            estimated_tokens=1000
        ))
        
        outline_id = tasks[-1].id
        
        tasks.append(Task(
            id=self._generate_task_id(),
            type=TaskType.WRITE_CHAPTER,
            title="撰寫章節內容",
            description="根據大綱撰寫完整章節",
            parameters={"goal": goal},
            dependencies=[outline_id],
            estimated_tokens=4000
        ))
        
        chapter_id = tasks[-1].id
        
        tasks.append(Task(
            id=self._generate_task_id(),
            type=TaskType.REVIEW_CONTENT,
            title="自我審查",
            description="檢查內容的一致性、流暢度和品質",
            parameters={"focus": ["consistency", "flow", "quality"]},
            dependencies=[chapter_id]
        ))
        
        review_id = tasks[-1].id
        
        tasks.append(Task(
            id=self._generate_task_id(),
            type=TaskType.IMPROVE_CONTENT,
            title="改進內容",
            description="根據審查結果改進章節",
            parameters={},
            dependencies=[review_id],
            estimated_tokens=2000
        ))
        
        return TaskPlan(
            id=plan_id,
            goal=goal,
            tasks=tasks,
            context=context or {}
        )
    
    async def _plan_write_outline(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for writing an outline."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="研究世界觀",
                description="檢索相關的世界設定",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_PLOT,
                title="分析現有情節",
                description="了解故事的發展方向和未解決的線索",
                parameters={"query": goal}
            ),
        ]
        
        research_ids = [t.id for t in tasks]
        
        tasks.append(Task(
            id=self._generate_task_id(),
            type=TaskType.WRITE_OUTLINE,
            title="創建大綱",
            description="撰寫詳細的內容大綱",
            parameters={"goal": goal},
            dependencies=research_ids,
            estimated_tokens=2000
        ))
        
        tasks.append(Task(
            id=self._generate_task_id(),
            type=TaskType.REVIEW_CONTENT,
            title="審查大綱",
            description="檢查大綱的邏輯性和完整性",
            dependencies=[tasks[-1].id]
        ))
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_write_scene(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for writing a scene."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_CHARACTERS,
                title="分析場景角色",
                description="了解場景中角色的狀態和動機",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.WRITE_SCENE,
                title="撰寫場景",
                description="創作生動的場景內容",
                parameters={"goal": goal},
                dependencies=[],
                estimated_tokens=2000
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="審查場景",
                description="確保場景的張力和流暢度",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_write_content(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Generic content writing plan."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="研究相關內容",
                description="檢索與目標相關的所有資訊",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.WRITE_CHAPTER,
                title="撰寫內容",
                description="根據目標創作內容",
                parameters={"goal": goal},
                dependencies=[],
                estimated_tokens=3000
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="審查內容",
                description="確保內容品質",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_consistency_check(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for consistency checking."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="載入世界觀規則",
                description="檢索所有世界觀設定和規則",
                parameters={"query": "世界觀 規則 設定", "limit": 50}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_CHARACTERS,
                title="載入角色設定",
                description="檢索所有角色資料",
                parameters={"query": "角色 人物 設定"}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.ANALYZE_CONSISTENCY,
                title="分析一致性",
                description="檢查內容與設定之間的矛盾",
                parameters={"goal": goal},
                dependencies=[]
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.SUMMARIZE,
                title="生成報告",
                description="整理發現的問題並提出建議",
                dependencies=[]
            ),
        ]
        tasks[2].dependencies = [tasks[0].id, tasks[1].id]
        tasks[3].dependencies = [tasks[2].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_pacing_analysis(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for pacing analysis."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_PLOT,
                title="載入章節內容",
                description="檢索要分析的章節",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.ANALYZE_PACING,
                title="分析節奏",
                description="分析敘事節奏、張力曲線和情緒起伏",
                parameters={"goal": goal},
                dependencies=[]
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.SUMMARIZE,
                title="生成分析報告",
                description="整理分析結果並提出改進建議",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_general_analysis(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for general analysis."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="收集相關資訊",
                description="檢索分析所需的資訊",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="執行分析",
                description="根據目標進行詳細分析",
                parameters={"goal": goal},
                dependencies=[]
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.SUMMARIZE,
                title="總結發現",
                description="整理分析結果",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_create_character(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for creating a character."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="研究世界觀",
                description="了解角色將存在的世界設定",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_CHARACTERS,
                title="分析現有角色",
                description="了解現有角色以確保新角色獨特",
                parameters={"query": "角色 人物"}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.CREATE_CHARACTER,
                title="設計角色",
                description="創建完整的角色檔案",
                parameters={"goal": goal},
                dependencies=[],
                estimated_tokens=2000
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="審查角色",
                description="確保角色與世界觀一致",
                dependencies=[]
            ),
        ]
        tasks[2].dependencies = [tasks[0].id, tasks[1].id]
        tasks[3].dependencies = [tasks[2].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_update_worldbuilding(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for updating worldbuilding."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="檢索現有設定",
                description="了解現有的世界觀設定",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.UPDATE_WORLDBUILDING,
                title="更新設定",
                description="添加或修改世界觀設定",
                parameters={"goal": goal},
                dependencies=[],
                estimated_tokens=1500
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.ANALYZE_CONSISTENCY,
                title="檢查一致性",
                description="確保新設定不與現有設定矛盾",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_improve_content(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Plan for improving content."""
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="檢索相關設定",
                description="確保改進符合世界觀",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="分析現有內容",
                description="找出需要改進的地方",
                parameters={"goal": goal},
                dependencies=[]
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.IMPROVE_CONTENT,
                title="改進內容",
                description="根據分析結果進行改進",
                parameters={"goal": goal},
                dependencies=[],
                estimated_tokens=3000
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="驗證改進",
                description="確認改進後的品質",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        tasks[3].dependencies = [tasks[2].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
    
    async def _plan_with_llm(self, plan_id: str, goal: str, context: Dict) -> TaskPlan:
        """Use LLM to create a custom plan for complex goals."""
        # For now, default to a generic research + execute + review pattern
        tasks = [
            Task(
                id=self._generate_task_id(),
                type=TaskType.RESEARCH_WORLDBUILDING,
                title="研究相關資訊",
                description="收集完成目標所需的資訊",
                parameters={"query": goal}
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.WRITE_CHAPTER,
                title="執行任務",
                description=f"完成目標：{goal}",
                parameters={"goal": goal},
                dependencies=[],
                estimated_tokens=3000
            ),
            Task(
                id=self._generate_task_id(),
                type=TaskType.REVIEW_CONTENT,
                title="審查結果",
                description="確保結果符合預期",
                dependencies=[]
            ),
        ]
        tasks[1].dependencies = [tasks[0].id]
        tasks[2].dependencies = [tasks[1].id]
        
        return TaskPlan(id=plan_id, goal=goal, tasks=tasks, context=context or {})
