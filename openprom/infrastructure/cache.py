"""Redis 缓存服务

版本：4.2.0
功能:
    - 对联分析结果缓存
    - 模型加载状态缓存
    - 配置缓存
"""

import json
import time
import threading
import logging
from functools import lru_cache
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

from openprom.utils.env_config import get_redis_url, is_cache_enabled

logger = logging.getLogger(__name__)


class CacheService:
    """缓存服务

    支持 Redis 和内存缓存两种模式。
    Redis 不可用时自动降级到内存缓存。
    内存缓存采用线程安全的 LRU 淘汰策略（按访问时间）。
    """

    def __init__(self, redis_url: Optional[str] = None, max_memory_size: int = 1000):
        self.redis_url = redis_url or get_redis_url()
        self._redis: Optional[redis.Redis] = None
        self._memory_cache: Dict[str, Any] = {}
        self._memory_expiry: Dict[str, float] = {}
        self._access_time: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._enabled = is_cache_enabled()
        self._max_memory_size = max_memory_size
        self._hit_count = 0
        self._miss_count = 0

        if self._enabled and REDIS_AVAILABLE:
            self._connect_redis()

    def _connect_redis(self):
        """连接 Redis"""
        try:
            self._redis = redis.from_url(
                self.redis_url, decode_responses=True, socket_connect_timeout=5, socket_timeout=5
            )
            self._redis.ping()
            logger.info(f"Redis 连接成功：{self.redis_url}")
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"Redis 连接失败，使用内存缓存：{e}")
            self._redis = None

    def _get_key(self, prefix: str, key: str) -> str:
        """生成缓存键"""
        return f"openprom:{prefix}:{key}"

    def _evict_lru(self):
        """LRU 淘汰：移除最久未被访问且未过期的条目"""
        if len(self._memory_cache) < self._max_memory_size:
            return

        now = time.time()
        candidates = []
        for k in list(self._memory_cache.keys()):
            if k not in self._memory_expiry or self._memory_expiry[k] >= now:
                candidates.append(k)

        if not candidates:
            expired = [
                k
                for k in list(self._memory_cache.keys())
                if k in self._memory_expiry and self._memory_expiry[k] < now
            ]
            for k in expired:
                self._memory_cache.pop(k, None)
                self._memory_expiry.pop(k, None)
                self._access_time.pop(k, None)
            return

        sorted_candidates = sorted(candidates, key=lambda k: self._access_time.get(k, 0))
        while len(self._memory_cache) >= self._max_memory_size and sorted_candidates:
            oldest = sorted_candidates.pop(0)
            self._memory_cache.pop(oldest, None)
            self._memory_expiry.pop(oldest, None)
            self._access_time.pop(oldest, None)

    def _purge_expired(self):
        """清除过期条目"""
        now = time.time()
        expired = [k for k in list(self._memory_expiry.keys()) if self._memory_expiry[k] < now]
        for k in expired:
            self._memory_cache.pop(k, None)
            self._memory_expiry.pop(k, None)
            self._access_time.pop(k, None)

    def get(self, prefix: str, key: str) -> Optional[Any]:
        """获取缓存"""
        cache_key = self._get_key(prefix, key)

        if self._redis:
            try:
                value = self._redis.get(cache_key)
                if value:
                    self._hit_count += 1
                    logger.debug(f"Redis 命中：{cache_key}")
                    return json.loads(value)
            except (RedisError, json.JSONDecodeError) as e:
                logger.warning(f"Redis 读取失败：{e}")

        with self._lock:
            self._purge_expired()
            if cache_key in self._memory_cache:
                self._hit_count += 1
                self._access_time[cache_key] = time.time()
                logger.debug(f"内存缓存命中：{cache_key}")
                return self._memory_cache[cache_key]

        self._miss_count += 1
        return None

    def set(self, prefix: str, key: str, value: Any, ttl: Optional[timedelta] = None):
        """设置缓存（带TTL和LRU淘汰）"""
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

        ttl_seconds = ttl.total_seconds() if ttl else 3600

        with self._lock:
            self._purge_expired()
            self._evict_lru()
            self._memory_cache[cache_key] = value
            self._memory_expiry[cache_key] = time.time() + ttl_seconds
            self._access_time[cache_key] = time.time()
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

        with self._lock:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                self._memory_expiry.pop(cache_key, None)
                self._access_time.pop(cache_key, None)
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

        prefix_key = f"openprom:{prefix}:"
        with self._lock:
            to_delete = [k for k in self._memory_cache if k.startswith(prefix_key)]
            for key in to_delete:
                del self._memory_cache[key]
                self._memory_expiry.pop(key, None)
                self._access_time.pop(key, None)

        logger.info(f"清除内存缓存：{len(to_delete)} 条")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0.0

        stats = {
            "enabled": self._enabled,
            "redis_connected": self._redis is not None,
            "memory_cache_size": len(self._memory_cache),
            "memory_cache_max": self._max_memory_size,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate_percent": round(hit_rate, 2),
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


@lru_cache(maxsize=1)
def get_cache_service() -> CacheService:
    """获取缓存服务实例（延迟初始化）"""
    return CacheService()


def get_cache_key_couplet(upper: str, lower: str) -> str:
    """生成对联缓存键"""
    import hashlib

    content = f"{upper}|{lower}"
    hash_value = hashlib.md5(content.encode("utf-8")).hexdigest()
    return f"couplet:{hash_value}"


def get_cache_key_meter(text: str, meter_type: str) -> str:
    """生成格律检测缓存键"""
    import hashlib

    content = f"{text}|{meter_type}"
    hash_value = hashlib.md5(content.encode("utf-8")).hexdigest()
    return f"meter:{hash_value}"
