"""Tasks layer router: list registered tasks, run them, inspect traces.

This is the L2 (Orchestration) HTTP surface envisioned in
doc/02-target-architecture.md. It makes the task system, AgentRunner, and
TaskTraceStore observable from the outside.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Query

from openprom.routers.common import (
    PormErrorCode,
    PormHTTPException,
    TaskListResponse,
    TaskRunRequest,
    TaskRunResponse,
    TraceDetailResponse,
    TraceListItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["任务编排"])


@router.get("", response_model=TaskListResponse, summary="列出所有已注册任务")
async def list_tasks() -> TaskListResponse:
    from openprom.agents import get_task_registry

    reg = get_task_registry()
    tasks = []
    for name, cfg in reg.items():
        tasks.append(
            {
                "name": cfg.name,
                "description": cfg.description,
                "tools": cfg.tools,
                "max_llm_rounds": cfg.max_llm_rounds,
                "use_rag": cfg.use_rag,
                "rag_task_type": cfg.rag_task_type,
                "use_saddle": cfg.use_saddle,
                "streaming": cfg.streaming,
                "temperature": cfg.temperature,
            }
        )
    return TaskListResponse(tasks=tasks)


@router.post("/run", response_model=TaskRunResponse, summary="通过 AgentRunner 执行任务")
async def run_task(req: TaskRunRequest) -> TaskRunResponse:
    from openprom.agents.runner import get_agent_runner

    runner = get_agent_runner()
    try:
        result = runner.run(
            task_name=req.task_name,
            user_prompt=req.user_prompt,
            system_prompt=req.system_prompt,
            max_rounds_override=req.max_rounds,
            extra_context=req.extra_context,
        )
    except ValueError as e:
        raise PormHTTPException(
            status_code=404,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Task run failed")
        raise PormHTTPException(
            status_code=500,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=f"Task execution failed: {e}",
        )

    trace = result["trace"]
    trace_d = trace.to_dict()
    return TaskRunResponse(
        content=result["content"],
        trace=TraceDetailResponse(
            task_id=trace_d["task_id"],
            task_name=trace_d["task_name"],
            started_at=_iso(trace_d.get("started_at")),
            finished_at=_iso(trace_d.get("finished_at")),
            total_duration_ms=trace_d["total_duration_ms"],
            llm_calls=trace_d["llm_calls"],
            tool_calls=trace_d["tool_calls"],
            rag_calls=trace_d["rag_calls"],
            success=trace_d["success"],
            error=trace_d.get("error"),
            steps=trace_d.get("steps", []),
        ),
    )


@router.get("/traces", response_model=List[TraceListItem], summary="最近的任务执行记录")
async def list_traces(
    limit: int = Query(default=20, ge=1, le=200),
) -> List[TraceListItem]:
    try:
        from openprom.infrastructure.task_trace import get_task_trace_store

        store = get_task_trace_store()
        rows = store.list_recent(limit=limit)
    except Exception as e:
        logger.exception("List traces failed")
        raise PormHTTPException(
            status_code=503,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=f"Trace store unavailable: {e}",
        )

    return [
        TraceListItem(
            task_id=r["task_id"],
            task_name=r["task_name"],
            started_at=r.get("started_at"),
            finished_at=r.get("finished_at"),
            total_duration_ms=r.get("total_duration_ms", 0.0),
            llm_calls=r.get("llm_calls", 0),
            tool_calls=r.get("tool_calls", 0),
            rag_calls=r.get("rag_calls", 0),
            success=r.get("success", False),
            error=r.get("error"),
        )
        for r in rows
    ]


@router.get(
    "/traces/{task_id}", response_model=TraceDetailResponse, summary="单条任务执行的完整轨迹"
)
async def get_trace(task_id: str) -> TraceDetailResponse:
    try:
        from openprom.infrastructure.task_trace import get_task_trace_store

        store = get_task_trace_store()
        row = store.get(task_id)
    except Exception as e:
        logger.exception("Get trace failed")
        raise PormHTTPException(
            status_code=503,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=f"Trace store unavailable: {e}",
        )

    if row is None:
        raise PormHTTPException(
            status_code=404,
            error_code=PormErrorCode.INTERNAL_ERROR,
            detail=f"Trace not found: {task_id}",
        )

    return TraceDetailResponse(
        task_id=row["task_id"],
        task_name=row["task_name"],
        started_at=row.get("started_at"),
        finished_at=row.get("finished_at"),
        total_duration_ms=row.get("total_duration_ms", 0.0),
        llm_calls=row.get("llm_calls", 0),
        tool_calls=row.get("tool_calls", 0),
        rag_calls=row.get("rag_calls", 0),
        success=row.get("success", False),
        error=row.get("error"),
        steps=row.get("steps", []),
    )


def _iso(ts):
    """Convert a timestamp float to ISO string."""
    if ts is None:
        return None
    from datetime import datetime

    return datetime.fromtimestamp(ts).isoformat()
