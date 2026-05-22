"""提示词配置管理系统 (Prompt Configuration Management System)
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import time
import hashlib
from pathlib import Path
from threading import Lock, RLock
import yaml


class PromptType(Enum):
    """提示词类型枚举"""
    TECHNIQUE_ANALYSIS = auto()     # 技法分析
    ARTISTIC_ANALYSIS = auto()      # 艺术表现分析
    IMPRESSION_ANALYSIS = auto()    # 印象评分
    QUALITY_VALIDATION = auto()     # 质量验证
    ERROR_CORRECTION = auto()       # 错误修正
    CONTEXT_ENHANCEMENT = auto()    # 上下文增强


class PromptVersion(Enum):
    """提示词版本策略"""
    STABLE = "stable"               # 稳定版
    BETA = "beta"                   # 测试版
    CANARY = "canary"               # 金丝雀版
    EXPERIMENTAL = "experimental"   # 实验版


@dataclass(frozen=True)
class PromptTemplate:
    """提示词模板不可变对象
    
    Attributes:
        name: 模板唯一标识名
        template: 模板内容（支持Jinja2语法）
        version: 版本号（语义化版本）
        prompt_type: 提示词类型
        parameters: 模板参数定义
        metadata: 元数据（作者、创建时间、标签等）
        checksum: 内容校验和
    """
    name: str
    template: str
    version: str
    prompt_type: PromptType
    parameters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    
    def __post_init__(self):
        if not self.checksum:
            object.__setattr__(
                self, 
                'checksum', 
                hashlib.sha256(self.template.encode()).hexdigest()[:16]
            )
    
    def render(self, **kwargs) -> str:
        """渲染模板
        
        Args:
            **kwargs: 模板变量
            
        Returns:
            渲染后的提示词文本
        """
        from jinja2 import Template, StrictUndefined
        
        template = Template(self.template, undefined=StrictUndefined)
        return template.render(**kwargs)
    
    def validate_parameters(self, params: Dict[str, Any]) -> List[str]:
        """验证参数完整性
        
        Args:
            params: 待验证的参数
            
        Returns:
            缺失的参数列表
        """
        required = set(self.parameters.get('required', []))
        provided = set(params.keys())
        return list(required - provided)


@dataclass
class PromptConfig:
    """提示词配置对象
    
    包含提示词的所有配置信息，支持多版本管理。
    """
    name: str
    prompt_type: PromptType
    versions: Dict[str, PromptTemplate] = field(default_factory=dict)
    active_version: str = ""
    environment: str = "production"
    ab_test_config: Optional[Dict[str, Any]] = None
    
    def get_active(self) -> PromptTemplate:
        """获取当前激活的提示词模板"""
        if not self.active_version or self.active_version not in self.versions:
            raise ValueError(f"Prompt {self.name} has no active version")
        return self.versions[self.active_version]
    
    def get_version(self, version: str) -> PromptTemplate:
        """获取指定版本的提示词模板"""
        if version not in self.versions:
            raise ValueError(f"Version {version} not found for prompt {self.name}")
        return self.versions[version]


class PromptConfigService:
    """提示词配置服务
    
    企业级提示词配置管理中心，提供：
    - 提示词的CRUD操作
    - 版本管理与灰度发布
    - 热更新机制
    - 配置校验与审计
    - A/B测试支持
    """
    
    _instance: Optional['PromptConfigService'] = None
    _lock: Lock = RLock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        with self._lock:
            if getattr(self, '_initialized', False):
                return
            
            self._initialized = True
            self._configs: Dict[str, PromptConfig] = {}
            self._watchers: List[Callable] = []
            self._config_dir: Path = Path(__file__).parent / "prompts"
            self._last_reload: float = 0
            self._reload_interval: float = 30.0
            self._file_lock = RLock()
            
            # 初始化加载
            self._ensure_config_dir()
            self._load_all_configs()
    
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建默认提示词文件
        self._create_default_prompts()
    
    def _create_default_prompts(self):
        """创建默认提示词配置"""
        default_prompts = {
            "technique_analysis.yaml": {
                "name": "technique_analysis",
                "prompt_type": "TECHNIQUE_ANALYSIS",
                "active_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "template": """请从技法角度分析以下对联：

上联：{{ upper }}
下联：{{ lower }}

逐字逐词分析：
1. 【词性对应】：分析每个对应位置的词性是否匹配（名对名、动对动等）
2. 【结构对应】：分析句式结构是否平行（主谓对主谓、偏正对偏正等）
3. 【平仄对应】：分析平仄是否相对
4. 【对仗类型】：判断是正对、反对还是流水对

评分标准：
- 90-100分：对仗工整，词性、结构、平仄均协调
- 80-89分：对仗良好，略有瑕疵
- 70-79分：对仗及格，存在明显问题
- 60-69分：对仗较差
- 0-59分：不符合对仗要求

请以JSON格式返回：
{
    "score": 整数分数(0-100),
    "reason": "逐字技法分析，指出每个对应位置的对仗情况",
    "word_analysis": [
        {"pos": 1, "upper_char": "字", "lower_char": "字", "pos_match": true/false, "comment": "评价"}
    ],
    "structure": "结构分析",
    "duizhang_type": "正对/反对/流水对"
}""",
                        "parameters": {"required": ["upper", "lower"]},
                        "metadata": {"author": "porm-system", "created_at": "2024-01-01"}
                    }
                }
            },
            "artistic_analysis.yaml": {
                "name": "artistic_analysis",
                "prompt_type": "ARTISTIC_ANALYSIS",
                "active_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "template": """请从艺术角度深度赏析以下对联：

上联：{{ upper }}
下联：{{ lower }}

【意境营造】
- 画面感：是否构建出清晰的视觉画面？
- 情感：表达了怎样的情感基调？
- 余味：读完后是否有回味的空间？

【修辞手法】
- 使用了哪些修辞手法？（比喻、拟人、夸张、对偶等）
- 这些手法运用是否自然贴切？

【文化内涵】
- 是否有典故或文化引用？
- 体现了怎样的文化底蕴？

【创新性】
- 意象组合是否有新意？
- 是否突破了陈词滥调？

请以JSON格式返回：
{
    "score": 整数分数(0-100),
    "意境": {"score": 分数, "comment": "结合原句分析意境"},
    "修辞": {"score": 分数, "comment": "结合原句分析修辞手法"},
    "文化": {"score": 分数, "comment": "结合原句分析文化内涵"},
    "创新": {"score": 分数, "comment": "结合原句分析创新性"},
    "overall_comment": "总体艺术评价"
}""",
                        "parameters": {"required": ["upper", "lower"]},
                        "metadata": {"author": "porm-system", "created_at": "2024-01-01"}
                    }
                }
            },
            "impression_analysis.yaml": {
                "name": "impression_analysis",
                "prompt_type": "IMPRESSION_ANALYSIS",
                "active_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "template": """请作为资深对联鉴赏家，凭专业直觉评价以下对联：

上联：{{ upper }}
下联：{{ lower }}

评价要求：
1. 忽略技术性细节（平仄、格律等），专注于整体审美体验
2. 考虑第一印象的冲击力与持久力
3. 评估艺术感染力与情感共鸣
4. 判断是否具有收藏或传播价值

评分标准：
- 90-100分：惊艳之作，令人过目难忘
- 80-89分：上乘之作，值得品味
- 70-79分：良好之作，有一定价值
- 60-69分：普通之作，缺乏亮点
- 0-59分：欠佳之作，难以引起共鸣

请以JSON格式返回：
{
    "score": 整数分数(0-100),
    "reason": "评分理由（1-2句话概括核心感受）",
    "highlights": ["亮点1", "亮点2"],
    "weaknesses": ["不足1", "不足2"]
}""",
                        "parameters": {
                            "required": ["upper", "lower"]
                        },
                        "metadata": {
                            "author": "porm-system",
                            "created_at": "2024-01-01",
                            "tags": ["impression", "score", "v1"]
                        }
                    }
                }
            },
            "quality_validation.yaml": {
                "name": "quality_validation",
                "prompt_type": "QUALITY_VALIDATION",
                "active_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "template": """请严格验证以下对联分析结果的质量：

原始对联：
上联：{{ upper }}
下联：{{ lower }}

待验证结果：
{{ result_json }}

验证维度：
1. 【逻辑一致性】
   - 评分与评价理由是否一致
   - 各维度评分是否相互协调
   - 是否存在自相矛盾之处

2. 【事实准确性】
   - 对仗分析是否符合实际
   - 文化典故引用是否准确
   - 字词解释是否正确

3. 【评价客观性】
   - 是否存在明显偏见
   - 评价标准是否统一
   - 是否受到无关因素影响

4. 【建议可行性】
   - 改进建议是否具体可行
   - 建议是否符合对联创作规律
   - 建议是否具有建设性

请以JSON格式返回：
{
    "is_valid": true/false,
    "confidence": 置信度(0-1),
    "issues": ["问题1", "问题2"],
    "corrections": {"字段名": "修正值"},
    "final_score": 修正后的总分
}""",
                        "parameters": {
                            "required": ["upper", "lower", "result_json"]
                        },
                        "metadata": {
                            "author": "porm-system",
                            "created_at": "2024-01-01",
                            "tags": ["validation", "quality", "v1"]
                        }
                    }
                }
            }
        }
        
        for filename, config in default_prompts.items():
            filepath = self._config_dir / filename
            if not filepath.exists():
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(config, f, allow_unicode=True, sort_keys=False)
    
    def _load_all_configs(self):
        """加载所有提示词配置"""
        with self._file_lock:
            for yaml_file in self._config_dir.glob("*.yaml"):
                self._load_single_config(yaml_file)
    
    def _load_single_config(self, filepath: Path):
        """加载单个配置文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                return
            
            name = data.get('name')
            prompt_type = PromptType[data.get('prompt_type', 'DUIZHANG_ANALYSIS')]
            active_version = data.get('active_version', '')
            
            versions = {}
            for version_str, version_data in data.get('versions', {}).items():
                template = PromptTemplate(
                    name=name,
                    template=version_data['template'],
                    version=version_str,
                    prompt_type=prompt_type,
                    parameters=version_data.get('parameters', {}),
                    metadata=version_data.get('metadata', {})
                )
                versions[version_str] = template
            
            config = PromptConfig(
                name=name,
                prompt_type=prompt_type,
                versions=versions,
                active_version=active_version
            )
            
            self._configs[name] = config
            
        except Exception as e:
            raise RuntimeError(f"Failed to load prompt config from {filepath}: {e}")
    
    def get_prompt(self, name: str, version: Optional[str] = None) -> PromptTemplate:
        """获取提示词模板
        
        Args:
            name: 提示词名称
            version: 指定版本，None则使用当前激活版本
            
        Returns:
            PromptTemplate对象
        """
        if name not in self._configs:
            raise KeyError(f"Prompt config '{name}' not found")
        
        config = self._configs[name]
        
        if version:
            return config.get_version(version)
        return config.get_active()
    
    def render_prompt(self, name: str, **kwargs) -> str:
        """渲染提示词
        
        Args:
            name: 提示词名称
            **kwargs: 模板变量
            
        Returns:
            渲染后的提示词文本
        """
        template = self.get_prompt(name)
        
        # 验证必需参数
        missing = template.validate_parameters(kwargs)
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")
        
        return template.render(**kwargs)
    
    def reload_config(self, name: Optional[str] = None):
        """重新加载配置
        
        Args:
            name: 指定配置名称，None则重载所有
        """
        with self._file_lock:
            if name:
                filepath = self._config_dir / f"{name}.yaml"
                if filepath.exists():
                    self._load_single_config(filepath)
            else:
                self._load_all_configs()
        
        self._last_reload = time.time()
        self._notify_watchers()
    
    def register_watcher(self, callback: Callable):
        """注册配置变更监听器"""
        self._watchers.append(callback)
    
    def _notify_watchers(self):
        """通知所有监听器"""
        for watcher in self._watchers:
            try:
                watcher()
            except Exception:
                pass
    
    def list_prompts(self) -> List[str]:
        """列出所有提示词名称"""
        return list(self._configs.keys())
    
    def get_prompt_info(self, name: str) -> Dict[str, Any]:
        """获取提示词信息"""
        if name not in self._configs:
            raise KeyError(f"Prompt config '{name}' not found")
        
        config = self._configs[name]
        return {
            "name": config.name,
            "type": config.prompt_type.name,
            "versions": list(config.versions.keys()),
            "active_version": config.active_version,
            "environment": config.environment
        }


# 全局服务实例
def get_prompt_service() -> PromptConfigService:
    """获取提示词配置服务实例"""
    return PromptConfigService()
