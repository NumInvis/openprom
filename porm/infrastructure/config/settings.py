"""配置加载器

版本：4.0.0
"""

import yaml
import threading
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class APIConfig:
    """API 配置"""
    max_retries: int = 3
    retry_delay: float = 2.0
    timeout: float = 180.0
    temperature_technique: float = 0.3
    temperature_artistic: float = 0.4
    temperature_impression: float = 0.4
    max_workers: int = 4
    first_api_timeout: int = 300
    model_timeout: int = 180


@dataclass
class ScoringConfig:
    """评分配置"""
    technique_weights: Dict[str, float] = field(default_factory=lambda: {
        'qwen_cosine': 0.60,
        'llm_technique': 0.20,
        'llm_rhetoric': 0.20
    })
    total_weights: Dict[str, float] = field(default_factory=lambda: {
        'formal': 0.30,
        'technique': 0.30,
        'artistic': 0.30,
        'impression': 0.10
    })
    grade_thresholds: Dict[str, int] = field(default_factory=lambda: {
        'excellent': 90,
        'good': 75,
        'pass': 60,
        'fail': 0
    })


@dataclass
class NormalizationConfig:
    """归一化配置"""
    mean: float = 0.80
    std: float = 0.10
    min_observed: float = 0.50
    max_observed: float = 0.95


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    max_char_size: int = 10000
    max_sentence_size: int = 2000
    ttl_seconds: int = 3600


@dataclass
class ModelConfig:
    """模型配置"""
    model_name: str = "Qwen3.5-9B-Instruct"
    cache_dir: str = "./models"
    use_gpu: bool = True
    batch_size: int = 32
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)


class Settings:
    """配置管理器"""

    _instance: Optional['Settings'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        with self._lock:
            if getattr(self, '_initialized', False):
                return

            self._config_path = config_path or self._find_config_file()
            self._load_config()
            self._initialized = True

    def _find_config_file(self) -> str:
        candidates = [
            "config/settings.yaml",
            "../config/settings.yaml",
            "D:/ai/porm/config/settings.yaml"
        ]

        for candidate in candidates:
            if Path(candidate).exists():
                return candidate

        return "config/settings.yaml"

    def _load_config(self):
        self._raw_config: Dict[str, Any] = {}

        if Path(self._config_path).exists():
            try:
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    self._raw_config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"警告：加载配置文件失败：{e}")

        self.api = self._parse_api_config()
        self.scoring = self._parse_scoring_config()
        self.model = self._parse_model_config()

    def _parse_api_config(self) -> APIConfig:
        api_dict = self._raw_config.get('api', {})

        return APIConfig(
            max_retries=api_dict.get('max_retries', 3),
            retry_delay=api_dict.get('retry_delay_seconds', 2.0),
            timeout=api_dict.get('timeout_seconds', 180.0),
            temperature_technique=api_dict.get('temperature_technique', 0.3),
            temperature_artistic=api_dict.get('temperature_artistic', 0.4),
            temperature_impression=api_dict.get('temperature_impression', 0.4),
            max_workers=api_dict.get('max_workers', 4),
            first_api_timeout=api_dict.get('first_api_timeout', 300),
            model_timeout=api_dict.get('model_timeout', 180)
        )

    def _parse_scoring_config(self) -> ScoringConfig:
        scoring_dict = self._raw_config.get('scoring', {})

        technique_weights = scoring_dict.get('technique_weights', {})
        total_weights = scoring_dict.get('total_weights', {})
        grade_thresholds = scoring_dict.get('grade_thresholds', {})

        return ScoringConfig(
            technique_weights={
                'qwen_cosine': technique_weights.get('qwen_cosine', 0.60),
                'llm_technique': technique_weights.get('llm_technique', 0.20),
                'llm_rhetoric': technique_weights.get('llm_rhetoric', 0.20)
            },
            total_weights={
                'formal': total_weights.get('formal', 0.30),
                'technique': total_weights.get('technique', 0.30),
                'artistic': total_weights.get('artistic', 0.30),
                'impression': total_weights.get('impression', 0.10)
            },
            grade_thresholds={
                'excellent': grade_thresholds.get('excellent', 90),
                'good': grade_thresholds.get('good', 75),
                'pass': grade_thresholds.get('pass', 60),
                'fail': grade_thresholds.get('fail', 0)
            }
        )

    def _parse_model_config(self) -> ModelConfig:
        model_dict = self._raw_config.get('model', {})
        norm_dict = model_dict.get('normalization', {})
        cache_dict = model_dict.get('cache', {})

        return ModelConfig(
            model_name=model_dict.get('model_name', 'Qwen3.5-9B-Instruct'),
            cache_dir=model_dict.get('cache_dir', './models'),
            use_gpu=model_dict.get('use_gpu', True),
            batch_size=model_dict.get('batch_size', 32),
            normalization=NormalizationConfig(
                mean=norm_dict.get('mean', 0.80),
                std=norm_dict.get('std', 0.10),
                min_observed=norm_dict.get('min_observed', 0.50),
                max_observed=norm_dict.get('max_observed', 0.95)
            ),
            cache=CacheConfig(
                enabled=cache_dict.get('enabled', True),
                max_char_size=cache_dict.get('max_char_size', 10000),
                max_sentence_size=cache_dict.get('max_sentence_size', 2000),
                ttl_seconds=cache_dict.get('ttl_seconds', 3600)
            )
        )

    def reload(self):
        self._initialized = False
        self.__init__(self._config_path)

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        value = self._raw_config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value


def get_settings() -> Settings:
    """获取配置实例"""
    return Settings()


if __name__ == "__main__":
    settings = get_settings()
    print(f"配置已加载：{settings._config_path}")
    print(f"模型：{settings.model.model_name}")
