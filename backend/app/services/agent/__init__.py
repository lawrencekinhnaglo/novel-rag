"""
Novel Writing Agent - Agentic AI for Novelists

This module implements an agentic system that can:
- Plan and decompose writing goals into tasks
- Execute tasks autonomously using various tools
- Self-review and iterate on output
- Learn from user feedback
- Proactively monitor story consistency
"""

from .core import NovelAgent, get_novel_agent
from .planner import TaskPlanner, Task, TaskPlan
from .executor import TaskExecutor
from .memory import AgentMemory
from .critic import SelfCritic
from .tools import AgentToolkit

__all__ = [
    "NovelAgent",
    "get_novel_agent",
    "TaskPlanner",
    "Task",
    "TaskPlan",
    "TaskExecutor",
    "AgentMemory",
    "SelfCritic",
    "AgentToolkit",
]
