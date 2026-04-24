"""Redis 缓存服务

版本：4.1.0
功能:
    - 对联分析结果缓存
    - 模型加载状态缓存
    - 配置缓存
"""

import json
import logging
from typing import Optional, Any, Dict
from datetime import timedelta

try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    RedisError = Exception
    RedisConnectionError = Exception

from porm.utils.env_config import get_redis_url, is_cache_enabled

logger = logging.getLogger(__name__)


class CacheService:
    """缓存服务
    
    支持 Redis 和内存缓存两种模式。
    Redis 不可用时自动降级到内存缓存。
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or get_redis_url()
        self._redis: Optional[redis.Redis] = None
        self._memory_cache: Dict[str, Any] = {}
        self._enabled = is_cache_enabled()
        
        if self._enabled and REDIS_AVAILABLE:
            self._connect_redis()
    
    def _connect_redis(self):
        """连接 Redis"""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self._redis.ping()
            logger.info(f"Redis 连接成功：{self.redis_url}")
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"Redis 连接失败，使用内存缓存：{e}")
            self._redis = None
    
    def _get_key(self, prefix: str, key: str) -> str:
        """生成缓存键"""
        return f"porm:{prefix}:{key}"
    
    def get(self, prefix: str, key: str) -> Optional[Any]:
        """获取缓存"""
        cache_key = self._get_key(prefix, key)
        
        if self._redis:
            try:
                value = self._redis.get(cache_key)
                if value:
                    logger.debug(f"Redis 命中：{cache_key}")
                    return json.loads(value)
            except (RedisError, json.JSONDecodeError) as e:
                logger.warning(f"Redis 读取失败：{e}")
        
        if cache_key in self._memory_cache:
            logger.debug(f"内存缓存命中：{cache_key}")
            return self._memory_cache[cache_key]
        
        return None
    
    def set(
        self,
        prefix: str,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ):
        """设置缓存"""
        if not self._enabled:
            return
        
        cache_key = self._get_key(prefix, key)
        
        if self._redis:
            try:
                serialized = json.dumps(value, ensure_ascii=False)
                ex = int(ttl.total_seconds()) if ttl else None
                self._redis.set(cache_key, serialized, ex=ex)
                logger.debug(f"Redis 缓存：{cache_key}, TTL={ttl}")
                return
            except (RedisError, TypeError) as e:
                logger.warning(f"Redis 写入失败：{e}")
        
        self._memory_cache[cache_key] = value
        logger.debug(f"内存缓存：{cache_key}")
    
    def delete(self, prefix: str, key: str) -> bool:
        """删除缓存"""
        cache_key = self._get_key(prefix, key)
        
        deleted = False
        
        if self._redis:
            try:
                deleted = bool(self._redis.delete(cache_key))
            except RedisError as e:
                logger.warning(f"Redis 删除失败：{e}")
        
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            deleted = True
        
        return deleted
    
    def clear(self, prefix: str):
        """清除指定前缀的所有缓存"""
        pattern = self._get_key(prefix, "*")
        
        if self._redis:
            try:
                keys = self._redis.keys(pattern)
                if keys:
                    self._redis.delete(*keys)
                    logger.info(f"清除 Redis 缓存：{len(keys)} 条")
            except RedisError as e:
                logger.warning(f"Redis 清除失败：{e}")
        
        to_delete = [k for k in self._memory_cache if k.startswith(f"porm:{prefix}:")]
        for key in to_delete:
            del self._memory_cache[key]
        
        logger.info(f"清除内存缓存：{len(to_delete)} 条")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        stats = {
            "enabled": self._enabled,
            "redis_connected": self._redis is not None,
            "memory_cache_size": len(self._memory_cache)
        }
        
        if self._redis:
            try:
                info = self._redis.info("memory")
                stats["redis_memory_used"] = info.get("used_memory_human", "N/A")
            except RedisError:
                pass
        
        return stats
    
    def health_check(self) -> bool:
        """健康检查"""
        if not self._enabled:
            return True
        
        if self._redis:
            try:
                return self._redis.ping()
            except RedisError:
                return False
        
        return True


cache_service = CacheService()


def get_cache_key_couplet(upper: str, lower: str) -> str:
    """生成对联缓存键"""
    import hashlib
    content = f"{upper}|{lower}"
    hash_value = hashlib.md5(content.encode('utf-8')).hexdigest()
    return f"couplet:{hash_value}"


def get_cache_key_meter(text: str, meter_type: str) -> str:
    """生成格律检测缓存键"""
    import hashlib
    content = f"{text}|{meter_type}"
    hash_value = hashlib.md5(content.encode('utf-8')).hexdigest()
    return f"meter:{hash_value}"
