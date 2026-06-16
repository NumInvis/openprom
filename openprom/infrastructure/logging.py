"""结构化日志服务

版本：4.2.0
功能:
    - JSON 格式日志
    - 日志级别配置
    - 上下文信息注入
"""

import json
import logging
import sys
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler

from openprom.utils.env_config import get_log_level, get_log_format


class JSONFormatter(logging.Formatter):
    """JSON 格式日志"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data
        
        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """文本格式日志（带颜色）"""
    
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return (
            f"{color}{timestamp} - {record.name} - {record.levelname} - "
            f"{record.getMessage()}{self.RESET}"
        )


def get_logger(name: str = "openprom") -> logging.Logger:
    """获取或创建logger（兼容logging.getLogger）"""
    return setup_logging(name=name)


def setup_logging(
    name: str = "openprom",
    level: Optional[str] = None,
    log_format: Optional[str] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5
) -> logging.Logger:
    """设置日志
    
    参数:
        name: 日志名称
        level: 日志级别
        log_format: 日志格式 (json/text)
        log_file: 日志文件路径
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的日志文件数量
    
    返回:
        配置好的 Logger 实例
    """
    level = level or get_log_level()
    log_format = log_format or get_log_format()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    if logger.handlers:
        return logger
    
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    logger.info(f"日志初始化完成 | 级别={level} | 格式={log_format}")
    
    return logger


class LogContext:
    """日志上下文管理器"""
    
    @staticmethod
    def add_fields(
        logger: logging.Logger,
        **kwargs
    ) -> logging.Logger:
        """添加上下文字段"""
        class ContextAdapter(logging.LoggerAdapter):
            def process(self, msg, kwargs):
                extra = kwargs.get('extra', {})
                extra.update(self.extra)
                kwargs['extra'] = extra
                return msg, kwargs
        
        return ContextAdapter(logger, kwargs)


def log_api_call(
    logger: logging.Logger,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    **extra
):
    """记录 API 调用日志"""
    logger.info(
        f"API 调用 | {method} {endpoint} | 状态={status_code} | 耗时={duration_ms:.2f}ms",
        extra={
            "extra_data": {
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "duration_ms": duration_ms,
                **extra
            }
        }
    )


def log_score_result(
    logger: logging.Logger,
    upper: str,
    lower: str,
    total_score: float,
    grade: str,
    duration_ms: float
):
    """记录评分结果"""
    logger.info(
        f"对联评分 | 上联={upper[:10]}... | 下联={lower[:10]}... | "
        f"分数={total_score} | 等级={grade} | 耗时={duration_ms:.2f}ms",
        extra={
            "extra_data": {
                "upper": upper,
                "lower": lower,
                "total_score": total_score,
                "grade": grade,
                "duration_ms": duration_ms
            }
        }
    )


def log_error_with_context(
    logger: logging.Logger,
    message: str,
    error: Exception,
    **context
):
    """记录错误日志（带上下文）"""
    logger.error(
        f"{message} | 错误={str(error)}",
        exc_info=True,
        extra={
            "extra_data": {
                "error_type": type(error).__name__,
                "error_message": str(error),
                **context
            }
        }
    )
