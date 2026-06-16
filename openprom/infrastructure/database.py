"""数据库模型和会话管理

版本：4.2.0
功能:
    - SQLAlchemy ORM 模型
    - 数据库会话管理
    - 数据迁移支持
"""

import logging
from datetime import datetime
from typing import Optional, List, Any, Dict
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    DateTime, JSON, Index, func
)
from sqlalchemy.orm import (
    declarative_base, sessionmaker
)
from sqlalchemy.pool import StaticPool

from openprom.utils.env_config import get_database_url

logger = logging.getLogger(__name__)

Base = declarative_base()


class CoupletAnalysis(Base):
    """对联分析记录"""
    __tablename__ = "couplet_analyses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    upper = Column(String(200), nullable=False, index=True)
    lower = Column(String(200), nullable=False, index=True)
    
    formal_score = Column(Float, default=0.0)
    technique_score = Column(Float, default=0.0)
    artistic_score = Column(Float, default=0.0)
    impression_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    grade = Column(String(20), default="")
    pingze_score = Column(Float, default=0.0)
    
    llm_evaluation = Column(JSON, default=dict)
    warnings = Column(JSON, default=list)
    comments = Column(JSON, default=dict)
    
    session_id = Column(String(64), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    is_public = Column(Integer, default=0)
    favorite = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.now, index=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        Index('idx_scores', 'total_score', 'grade'),
        Index('idx_created', 'created_at'),
        Index('idx_session', 'session_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "upper": self.upper,
            "lower": self.lower,
            "formal_score": self.formal_score,
            "technique_score": self.technique_score,
            "artistic_score": self.artistic_score,
            "impression_score": self.impression_score,
            "total_score": self.total_score,
            "grade": self.grade,
            "pingze_score": self.pingze_score,
            "llm_evaluation": self.llm_evaluation,
            "warnings": self.warnings,
            "comments": self.comments,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_score(cls, score_result, **kwargs) -> "CoupletAnalysis":
        """从评分结果创建记录"""
        return cls(
            upper=score_result.upper,
            lower=score_result.lower,
            formal_score=score_result.formal_score,
            technique_score=score_result.technique_score,
            artistic_score=score_result.artistic_score,
            impression_score=score_result.impression_score,
            total_score=score_result.total_score,
            grade=score_result.grade,
            pingze_score=score_result.pingze_score,
            llm_evaluation={
                "technique": score_result.llm_technique_evaluation,
                "rhetoric": score_result.llm_rhetoric_evaluation
            },
            warnings=score_result.warnings,
            comments=score_result.comments,
            **kwargs
        )


class MeterCheck(Base):
    """格律检测记录"""
    __tablename__ = "meter_checks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(500), nullable=False)
    meter_type = Column(String(20), nullable=False)
    matched_meter = Column(String(100))
    match_rate = Column(Float, default=0.0)
    pingze_sequence = Column(JSON, default=list)
    violations = Column(JSON, default=list)
    is_compliant = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    __table_args__ = (
        Index('idx_meter_type', 'meter_type', 'is_compliant'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "meter_type": self.meter_type,
            "matched_meter": self.matched_meter,
            "match_rate": self.match_rate,
            "pingze_sequence": self.pingze_sequence,
            "violations": self.violations,
            "is_compliant": bool(self.is_compliant),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UserSession(Base):
    """用户会话"""
    __tablename__ = "user_sessions"
    
    id = Column(String(64), primary_key=True)
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    ip_hash = Column(String(64), nullable=True)
    user_agent_hash = Column(String(64), nullable=True)


class UserFeedback(Base):
    """用户反馈"""
    __tablename__ = "user_feedbacks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), index=True, nullable=True)
    analysis_id = Column(Integer, index=True, nullable=True)
    feedback_type = Column(String(20), default="")
    content = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)


class DailyBest(Base):
    """每日佳作"""
    __tablename__ = "daily_bests"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), index=True, unique=True)
    analysis_id = Column(Integer, nullable=True)
    total_score = Column(Float, default=0.0)
    category = Column(String(20), default="daily")


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or get_database_url()
        logger.info(f"使用数据库：{self.database_url}")
        
        connect_args = {}
        if self.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        
        self.engine = create_engine(
            self.database_url,
            connect_args=connect_args,
            poolclass=StaticPool if self.database_url.startswith("sqlite") else None,
            echo=False
        )
        
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        self.SessionLocal = SessionLocal
    
    def create_tables(self):
        """创建所有表"""
        logger.info("创建数据库表...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("数据库表创建完成")
    
    def drop_tables(self):
        """删除所有表（慎用）"""
        logger.warning("删除所有数据库表...")
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self):
        """获取数据库会话上下文"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"数据库操作失败：{e}", exc_info=True)
            raise
        finally:
            session.close()
    
    def save_couplet_analysis(self, score_result) -> CoupletAnalysis:
        """保存对联分析结果"""
        with self.get_session() as session:
            record = CoupletAnalysis.from_score(score_result)
            session.add(record)
            session.flush()
            logger.debug(f"保存对联分析记录：ID={record.id}")
            # Detach from session so it can be used after context exits
            session.expunge(record)
            return record
    
    def get_couplet_analysis(self, record_id: int) -> Optional[CoupletAnalysis]:
        """获取对联分析记录"""
        with self.get_session() as session:
            record = session.get(CoupletAnalysis, record_id)
            if record:
                session.expunge(record)
            return record
    
    def get_couplet_history(
        self,
        limit: int = 50,
        offset: int = 0,
        session_id: Optional[str] = None
    ) -> List[CoupletAnalysis]:
        """获取历史记录"""
        with self.get_session() as session:
            query = session.query(CoupletAnalysis)
            if session_id is not None:
                query = query.filter(CoupletAnalysis.session_id == session_id)
            records = query\
                .order_by(CoupletAnalysis.created_at.desc())\
                .offset(offset)\
                .limit(limit)\
                .all()
            for r in records:
                session.expunge(r)
            return records
    
    def search_couplets(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[CoupletAnalysis]:
        """搜索对联"""
        with self.get_session() as session:
            pattern = f"%{keyword}%"
            records = session.query(CoupletAnalysis)\
                .filter(
                    (CoupletAnalysis.upper.like(pattern)) |
                    (CoupletAnalysis.lower.like(pattern))
                )\
                .order_by(CoupletAnalysis.created_at.desc())\
                .limit(limit)\
                .all()
            for r in records:
                session.expunge(r)
            return records
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.get_session() as session:
            total = session.query(func.count(CoupletAnalysis.id)).scalar()
            avg_score = session.query(func.avg(CoupletAnalysis.total_score)).scalar()
            
            grade_dist = session.query(
                CoupletAnalysis.grade,
                func.count(CoupletAnalysis.id)
            ).group_by(CoupletAnalysis.grade).all()
            
            return {
                "total_analyses": total or 0,
                "average_score": round(avg_score, 2) if avg_score else 0.0,
                "grade_distribution": dict(grade_dist)
            }
    
    def save_meter_check(self, meter_result: dict) -> MeterCheck:
        """保存格律检测结果"""
        with self.get_session() as session:
            record = MeterCheck(
                text=meter_result.get("text", ""),
                meter_type=meter_result.get("meter_type", "shi"),
                matched_meter=meter_result.get("matched_meter", ""),
                match_rate=meter_result.get("match_rate", 0.0),
                pingze_sequence=meter_result.get("pingze_sequence", []),
                violations=meter_result.get("violations", []),
                is_compliant=1 if meter_result.get("is_compliant", True) else 0
            )
            session.add(record)
            session.flush()
            return record




@lru_cache(maxsize=1)
def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例（延迟初始化）"""
    return DatabaseManager()
