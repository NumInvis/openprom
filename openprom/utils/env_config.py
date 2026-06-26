"""配置管理 - 支持环境变量

版本：4.2.0
功能：
    - 从环境变量加载配置
    - 回退到配置文件
    - 敏感信息管理
"""

import os
import json
import logging
from pathlib import Path

try:
    from dotenv import load_dotenv

    _project_root = Path(__file__).parent.parent.parent
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=True)
except Exception:
    pass

logger = logging.getLogger(__name__)


def get_api_key() -> str:
    """从环境变量或配置文件获取 API 密钥"""
    api_key = os.getenv("OPENPROM_API_KEY")

    if api_key:
        return api_key

    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("api_key", "")
        except Exception as e:
            logger.warning(f"读取配置文件失败：{e}")

    return ""


def get_base_url() -> str:
    """从环境变量或配置文件获取 Base URL"""
    base_url = os.getenv("OPENPROM_BASE_URL")

    if base_url:
        return base_url

    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("base_url", "")
        except Exception as e:
            logger.warning(f"读取配置文件失败：{e}")

    return "https://your-llm-gateway.example.com/ai/v1"


def get_model() -> str:
    """从环境变量或配置文件获取模型名称"""
    model = os.getenv("OPENPROM_MODEL")

    if model:
        return model

    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("model", "Qwen3.5-9B-Instruct")
        except Exception as e:
            logger.warning(f"读取配置文件失败：{e}")

    return "qwen3.7-plus"


def get_database_url() -> str:
    """获取数据库连接 URL"""
    return os.getenv("OPENPROM_DATABASE_URL", "sqlite:///./openprom.db")


def get_redis_url() -> str:
    """获取 Redis 连接 URL"""
    return os.getenv("OPENPROM_REDIS_URL", "redis://localhost:6379/0")


def is_cache_enabled() -> bool:
    """检查缓存是否启用"""
    return os.getenv("OPENPROM_CACHE_ENABLED", "false").lower() == "true"


def get_log_level() -> str:
    """获取日志级别"""
    return os.getenv("OPENPROM_LOG_LEVEL", "INFO").upper()


def get_log_format() -> str:
    """获取日志格式"""
    return os.getenv("OPENPROM_LOG_FORMAT", "text").lower()


def get_host() -> str:
    """获取服务监听地址"""
    return os.getenv("OPENPROM_HOST", "0.0.0.0")


def get_port() -> int:
    """获取服务端口"""
    try:
        return int(os.getenv("OPENPROM_PORT", "8000"))
    except ValueError:
        return 8000


def is_debug() -> bool:
    """检查是否调试模式"""
    return os.getenv("OPENPROM_DEBUG", "false").lower() == "true"


def get_config_value(key: str, type_: type = str, default=None):
    """统一配置入口

    按优先级读取：环境变量 > config.json > 默认值

    Args:
        key: 配置键名（如 'api_key', 'base_url'）
        type_: 期望类型
        default: 默认值

    Returns:
        配置值
    """
    env_map = {
        "api_key": "OPENPROM_API_KEY",
        "base_url": "OPENPROM_BASE_URL",
        "model": "OPENPROM_MODEL",
        "database_url": "OPENPROM_DATABASE_URL",
        "redis_url": "OPENPROM_REDIS_URL",
        "cache_enabled": "OPENPROM_CACHE_ENABLED",
        "log_level": "OPENPROM_LOG_LEVEL",
        "log_format": "OPENPROM_LOG_FORMAT",
        "host": "OPENPROM_HOST",
        "port": "OPENPROM_PORT",
        "debug": "OPENPROM_DEBUG",
    }

    env_name = env_map.get(key)
    if env_name:
        val = os.getenv(env_name)
        if val is not None:
            if type_ is bool:
                return val.lower() == "true"
            if type_ is int:
                try:
                    return int(val)
                except ValueError:
                    pass
            return val

    # 回退到 config.json
    config_path = Path(__file__).parent.parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                val = config.get(key)
                if val is not None:
                    return val
        except Exception:
            pass

    return default


def get_config() -> dict:
    """获取完整配置"""
    return {
        "api_key": get_api_key(),
        "base_url": get_base_url(),
        "model": get_model(),
        "database_url": get_database_url(),
        "redis_url": get_redis_url(),
        "cache_enabled": is_cache_enabled(),
        "log_level": get_log_level(),
        "log_format": get_log_format(),
        "host": get_host(),
        "port": get_port(),
        "debug": is_debug(),
    }
