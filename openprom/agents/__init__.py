"""Orchestration layer: TaskRegistry + AgentRunner.

Abstracts the tool-calling loop from individual generators into reusable
task templates. Each task declares: which tools, how many LLM rounds,
whether to use RAG, whether to apply Saddle QC, whether streaming.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskConfig:
    """Declaration of a task's orchestration parameters."""

    name: str
    description: str = ""
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)
    max_llm_rounds: int = 3
    use_rag: bool = True
    rag_task_type: str = "general"
    use_saddle: bool = False
    streaming: bool = True
    temperature: float = 0.7


@dataclass
class TaskStep:
    """A single step in a task trace."""

    step_type: str
    """'llm_call', 'tool_call', 'rag_retrieval', 'saddle_check', 'result'."""
    timestamp: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class TaskTrace:
    """Full trace of a single task execution."""

    task_name: str
    task_id: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    steps: List[TaskStep] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None

    def add_step(self, step_type: str, data: Dict[str, Any], duration_ms: float = 0.0):
        self.steps.append(TaskStep(
            step_type=step_type,
            timestamp=time.time(),
            data=data,
            duration_ms=duration_ms,
        ))

    @property
    def total_duration_ms(self) -> float:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at) * 1000
        return sum(s.duration_ms for s in self.steps)

    @property
    def llm_calls(self) -> int:
        return sum(1 for s in self.steps if s.step_type == "llm_call")

    @property
    def tool_calls(self) -> int:
        return sum(1 for s in self.steps if s.step_type == "tool_call")

    @property
    def rag_calls(self) -> int:
        return sum(1 for s in self.steps if s.step_type == "rag_retrieval")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "task_id": self.task_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_duration_ms": self.total_duration_ms,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "rag_calls": self.rag_calls,
            "success": self.success,
            "error": self.error,
            "steps": [
                {"type": s.step_type, "data": s.data, "duration_ms": s.duration_ms}
                for s in self.steps
            ],
        }


class TaskRegistry:
    """Registry of task configurations."""

    def __init__(self):
        self._tasks: Dict[str, TaskConfig] = {}

    def register(self, config: TaskConfig) -> None:
        self._tasks[config.name] = config

    def get(self, name: str) -> Optional[TaskConfig]:
        return self._tasks.get(name)

    def list_tasks(self) -> List[str]:
        return list(self._tasks.keys())

    def items(self):
        return self._tasks.items()


_global_registry: Optional[TaskRegistry] = None


def get_task_registry() -> TaskRegistry:
    global _global_registry
    if _global_registry is not None:
        return _global_registry
    registry = TaskRegistry()

    from openprom.infrastructure.config.settings import get_settings
    settings = get_settings()

    registry.register(TaskConfig(
        name="generate_couplet",
        description="对联生成",
        tools=["check_meter", "retrieve_poetry", "web_search", "self_critique"],
        max_llm_rounds=settings.generation.couplet_max_revision_rounds,
        use_rag=False,
        rag_task_type="generate_couplet",
        temperature=settings.api.temperature_generation,
    ))

    registry.register(TaskConfig(
        name="complete_couplet",
        description="对联补全",
        tools=["check_meter", "retrieve_poetry", "web_search", "self_critique"],
        max_llm_rounds=settings.generation.couplet_max_revision_rounds,
        use_rag=False,
        rag_task_type="generate_couplet",
        temperature=settings.api.temperature_generation,
    ))

    registry.register(TaskConfig(
        name="generate_shi",
        description="律诗生成",
        tools=["check_meter", "retrieve_poetry", "web_search", "self_critique"],
        max_llm_rounds=settings.generation.shi_max_revision_rounds,
        use_rag=False,
        rag_task_type="generate_shi",
        temperature=settings.api.temperature_generation,
    ))

    registry.register(TaskConfig(
        name="complete_shi",
        description="律诗补全",
        tools=["check_meter", "retrieve_poetry", "web_search", "self_critique"],
        max_llm_rounds=settings.generation.shi_max_revision_rounds,
        use_rag=False,
        rag_task_type="generate_shi",
        temperature=settings.api.temperature_generation,
    ))

    registry.register(TaskConfig(
        name="analyze_couplet",
        description="对联评分",
        tools=["check_meter"],
        max_llm_rounds=2,
        use_rag=False,
        use_saddle=True,
        temperature=settings.api.temperature_technique,
    ))

    _global_registry = registry
    return registry


def reset_task_registry() -> None:
    """Reset the singleton (for testing)."""
    global _global_registry
    _global_registry = None


__all__ = [
    "TaskConfig",
    "TaskStep",
    "TaskTrace",
    "TaskRegistry",
    "get_task_registry",
    "reset_task_registry",
]
