"""配置加载器

版本：4.2.0
"""

import yaml
import threading
from typing import Dict, Any, Optional, List
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
    temperature_generation: float = 0.7
    max_workers: int = 4
    first_api_timeout: int = 300
    model_timeout: int = 180


@dataclass
class ScoringConfig:
    """评分配置"""
    technique_weights: Dict[str, float] = field(default_factory=lambda: {
        'llm_technique': 0.50,
        'llm_rhetoric': 0.50
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
class ToolsConfig:
    """工具链配置"""
    meter_match_rate_threshold: float = 0.85
    meter_strict_match_rate_threshold: float = 0.95
    rhyme_book: str = "平水韵"
    rhyme_max_suggestions: int = 8
    rhyme_common_chars_weight: float = 1.2


@dataclass
class GenerationConfig:
    """生成/补全配置"""
    couplet_max_revision_rounds: int = 3
    couplet_default_length: int = 7
    shi_max_revision_rounds: int = 4
    shi_default_form: str = "七律"
    shi_supported_forms: List[str] = field(default_factory=lambda: ["五绝", "七绝", "五律", "七律"])
    streaming_enabled: bool = True
    streaming_keep_alive: bool = True


@dataclass
class AgentConfig:
    """Agent 配置"""
    enable_self_revision: bool = True
    deliver_best_effort: bool = True


@dataclass
class RAGConfig:
    """RAG / knowledge vector layer config"""
    enabled: bool = True
    embedding_provider: str = "sentence_transformers"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"
    vector_store_dir: str = "./openprom/data/vector_store"
    vector_store_collection: str = "poetry_knowledge"
    retrieve_top_k: int = 3
    filter_by_form: bool = True
    allow_empty_store: bool = True


@dataclass
class HermesConfig:
    """Hermes retrieval & skill layer config"""
    enabled: bool = True
    top_k: int = 3
    enable_hybrid: bool = True
    vector_weight: float = 1.0
    keyword_weight: float = 1.0
    rrf_k: int = 60
    chunk_whole_poem: bool = True
    chunk_couplets: bool = True
    chunk_quatrains: bool = True


@dataclass
class KnowledgeRetrievalConfig:
    """Knowledge layer retrieval sub-config."""
    strategy: str = "hybrid"
    top_k_recall: int = 20
    top_k_final: int = 5
    rerank_enabled: bool = False
    rerank_provider: str = "noop"
    rerank_weight_semantic: float = 0.6
    rerank_weight_rule: float = 0.4
    fusion_method: str = "rrf"
    rrf_k: int = 60


@dataclass
class KnowledgeEmbeddingConfig:
    """Knowledge layer embedding sub-config."""
    provider: str = "sentence_transformers"
    model: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cpu"


@dataclass
class KnowledgeMemoryConfig:
    """Knowledge layer memory sub-config."""
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    min_score: int = 75


@dataclass
class KnowledgeCorpusConfig:
    """Knowledge layer corpus sub-config."""
    active_snapshot: str = ""
    fallback_on_empty: bool = True


@dataclass
class KnowledgeConfig:
    """Knowledge layer v2 config (Hermes upgrade)."""
    enabled: bool = False
    retrieval: KnowledgeRetrievalConfig = field(default_factory=KnowledgeRetrievalConfig)
    embedding: KnowledgeEmbeddingConfig = field(default_factory=KnowledgeEmbeddingConfig)
    memory: KnowledgeMemoryConfig = field(default_factory=KnowledgeMemoryConfig)
    corpus: KnowledgeCorpusConfig = field(default_factory=KnowledgeCorpusConfig)


@dataclass
class FeaturesConfig:
    """Feature flags."""
    knowledge_layer_v2: bool = False
    saddle_engineering_enabled: bool = True
    saddle_strict_mode: bool = False
    saddle_max_violations: int = 3


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
        self.tools = self._parse_tools_config()
        self.generation = self._parse_generation_config()
        self.agent = self._parse_agent_config()
        self.rag = self._parse_rag_config()
        self.hermes = self._parse_hermes_config()
        self.knowledge = self._parse_knowledge_config()
        self.features = self._parse_features_config()

    def _parse_api_config(self) -> APIConfig:
        api_dict = self._raw_config.get('api', {})

        return APIConfig(
            max_retries=api_dict.get('max_retries', 3),
            retry_delay=api_dict.get('retry_delay_seconds', 2.0),
            timeout=api_dict.get('timeout_seconds', 180.0),
            temperature_technique=api_dict.get('temperature_technique', 0.3),
            temperature_artistic=api_dict.get('temperature_artistic', 0.4),
            temperature_impression=api_dict.get('temperature_impression', 0.4),
            temperature_generation=api_dict.get('temperature_generation', 0.7),
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
                'llm_technique': technique_weights.get('llm_technique', 0.50),
                'llm_rhetoric': technique_weights.get('llm_rhetoric', 0.50)
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

    def _parse_tools_config(self) -> ToolsConfig:
        tools_dict = self._raw_config.get('tools', {})
        meter_dict = tools_dict.get('meter', {})
        rhyme_dict = tools_dict.get('rhyme', {})
        return ToolsConfig(
            meter_match_rate_threshold=meter_dict.get('match_rate_threshold', 0.85),
            meter_strict_match_rate_threshold=meter_dict.get('strict_match_rate_threshold', 0.95),
            rhyme_book=rhyme_dict.get('book', '平水韵'),
            rhyme_max_suggestions=rhyme_dict.get('max_suggestions', 8),
            rhyme_common_chars_weight=rhyme_dict.get('common_chars_weight', 1.2)
        )

    def _parse_generation_config(self) -> GenerationConfig:
        gen_dict = self._raw_config.get('generation', {})
        couplet_dict = gen_dict.get('couplet', {})
        shi_dict = gen_dict.get('shi', {})
        stream_dict = gen_dict.get('streaming', {})
        return GenerationConfig(
            couplet_max_revision_rounds=couplet_dict.get('max_revision_rounds', 3),
            couplet_default_length=couplet_dict.get('default_length', 7),
            shi_max_revision_rounds=shi_dict.get('max_revision_rounds', 4),
            shi_default_form=shi_dict.get('default_form', '七律'),
            shi_supported_forms=shi_dict.get('supported_forms', ["五绝", "七绝", "五律", "七律"]),
            streaming_enabled=stream_dict.get('enabled', True),
            streaming_keep_alive=stream_dict.get('keep_alive_comment', True)
        )

    def _parse_agent_config(self) -> AgentConfig:
        agent_dict = self._raw_config.get('agent', {})
        return AgentConfig(
            enable_self_revision=agent_dict.get('enable_self_revision', True),
            deliver_best_effort=agent_dict.get('deliver_best_effort', True)
        )

    def _parse_rag_config(self) -> RAGConfig:
        rag_dict = self._raw_config.get('rag', {})
        return RAGConfig(
            enabled=rag_dict.get('enabled', True),
            embedding_provider=rag_dict.get('embedding_provider', 'sentence_transformers'),
            embedding_model=rag_dict.get('embedding_model', 'BAAI/bge-small-zh-v1.5'),
            embedding_device=rag_dict.get('embedding_device', 'cpu'),
            vector_store_dir=rag_dict.get('vector_store_dir', './openprom/data/vector_store'),
            vector_store_collection=rag_dict.get('vector_store_collection', 'poetry_knowledge'),
            retrieve_top_k=rag_dict.get('retrieve_top_k', 3),
            filter_by_form=rag_dict.get('filter_by_form', True),
            allow_empty_store=rag_dict.get('allow_empty_store', True)
        )

    def _parse_hermes_config(self) -> HermesConfig:
        h_dict = self._raw_config.get('hermes', {})
        return HermesConfig(
            enabled=h_dict.get('enabled', True),
            top_k=h_dict.get('top_k', 3),
            enable_hybrid=h_dict.get('enable_hybrid', True),
            vector_weight=h_dict.get('vector_weight', 1.0),
            keyword_weight=h_dict.get('keyword_weight', 1.0),
            rrf_k=h_dict.get('rrf_k', 60),
            chunk_whole_poem=h_dict.get('chunk_whole_poem', True),
            chunk_couplets=h_dict.get('chunk_couplets', True),
            chunk_quatrains=h_dict.get('chunk_quatrains', True),
        )

    def _parse_knowledge_config(self) -> KnowledgeConfig:
        k_dict = self._raw_config.get('knowledge', {})
        ret_dict = k_dict.get('retrieval', {})
        rerank_dict = ret_dict.get('rerank', {})
        weights_dict = rerank_dict.get('weights', {})
        fusion_dict = ret_dict.get('fusion', {})
        emb_dict = k_dict.get('embedding', {})
        mem_dict = k_dict.get('memory', {})
        corp_dict = k_dict.get('corpus', {})
        return KnowledgeConfig(
            enabled=k_dict.get('enabled', False),
            retrieval=KnowledgeRetrievalConfig(
                strategy=ret_dict.get('strategy', 'hybrid'),
                top_k_recall=ret_dict.get('top_k_recall', 20),
                top_k_final=ret_dict.get('top_k_final', 5),
                rerank_enabled=rerank_dict.get('enabled', False),
                rerank_provider=rerank_dict.get('provider', 'noop'),
                rerank_weight_semantic=weights_dict.get('semantic', 0.6),
                rerank_weight_rule=weights_dict.get('rule', 0.4),
                fusion_method=fusion_dict.get('method', 'rrf'),
                rrf_k=fusion_dict.get('rrf_k', 60),
            ),
            embedding=KnowledgeEmbeddingConfig(
                provider=emb_dict.get('provider', 'sentence_transformers'),
                model=emb_dict.get('model', 'BAAI/bge-small-zh-v1.5'),
                device=emb_dict.get('device', 'cpu'),
            ),
            memory=KnowledgeMemoryConfig(
                cache_enabled=mem_dict.get('cache_enabled', True),
                cache_ttl_seconds=mem_dict.get('cache_ttl_seconds', 3600),
                min_score=mem_dict.get('min_score', 75),
            ),
            corpus=KnowledgeCorpusConfig(
                active_snapshot=corp_dict.get('active_snapshot', ''),
                fallback_on_empty=corp_dict.get('fallback_on_empty', True),
            ),
        )

    def _parse_features_config(self) -> FeaturesConfig:
        feat = self._raw_config.get('features', {})
        saddle = feat.get('saddle_engineering', {})
        return FeaturesConfig(
            knowledge_layer_v2=feat.get('knowledge_layer_v2', False),
            saddle_engineering_enabled=saddle.get('enabled', True),
            saddle_strict_mode=saddle.get('strict_mode', False),
            saddle_max_violations=saddle.get('max_violations', 3),
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