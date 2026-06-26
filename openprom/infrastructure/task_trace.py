"""Task trace persistence to SQLite.

Stores TaskTrace execution data as JSON for later analysis.
"""

import json
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, String, Float, Integer, DateTime, Text

from openprom.infrastructure.database import Base, get_db_manager

logger = logging.getLogger(__name__)


class TaskTraceRow(Base):
    __tablename__ = "task_trace"

    task_id = Column(String(64), primary_key=True)
    task_name = Column(String(128), nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    total_duration_ms = Column(Float, default=0.0)
    llm_calls = Column(Integer, default=0)
    tool_calls = Column(Integer, default=0)
    rag_calls = Column(Integer, default=0)
    success = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    steps_json = Column(Text, default="[]")


class TaskTraceStore:
    def __init__(self, db_manager=None):
        self._db = db_manager or get_db_manager()

    def save(self, trace) -> None:
        started = datetime.fromtimestamp(trace.started_at) if trace.started_at else None
        finished = datetime.fromtimestamp(trace.finished_at) if trace.finished_at else None
        steps_data = [
            {"type": s.step_type, "data": s.data, "duration_ms": s.duration_ms} for s in trace.steps
        ]
        row = TaskTraceRow(
            task_id=trace.task_id,
            task_name=trace.task_name,
            started_at=started,
            finished_at=finished,
            total_duration_ms=trace.total_duration_ms,
            llm_calls=trace.llm_calls,
            tool_calls=trace.tool_calls,
            rag_calls=trace.rag_calls,
            success=1 if trace.success else 0,
            error=trace.error,
            steps_json=json.dumps(steps_data, ensure_ascii=False),
        )
        with self._db.get_session() as session:
            session.merge(row)
            session.flush()
            logger.debug("Saved task trace: %s", trace.task_id)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._db.get_session() as session:
            row = session.get(TaskTraceRow, task_id)
            if row is None:
                return None
            return self._row_to_dict(row)

    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._db.get_session() as session:
            rows = (
                session.query(TaskTraceRow)
                .order_by(TaskTraceRow.started_at.desc())
                .limit(limit)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: TaskTraceRow) -> Dict[str, Any]:
        return {
            "task_id": row.task_id,
            "task_name": row.task_name,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "total_duration_ms": row.total_duration_ms,
            "llm_calls": row.llm_calls,
            "tool_calls": row.tool_calls,
            "rag_calls": row.rag_calls,
            "success": bool(row.success),
            "error": row.error,
            "steps": json.loads(row.steps_json) if row.steps_json else [],
        }


@lru_cache(maxsize=1)
def get_task_trace_store() -> TaskTraceStore:
    return TaskTraceStore()
