"""马鞍工程控制机制 (Saddle Engineering Control System)

实现对LLM输出的精确控制与约束，确保系统输出的可控性、一致性和精确性。
"马鞍"比喻对LLM这匹"野马"的驾驭能力。

核心设计原则：
1. 多层控制：输入控制 -> 过程控制 -> 输出控制
2. 数学严谨：所有控制算法基于严格的数学模型
3. 相互制约：NLP、LLM、数学算法、格律规则相互验证
4. 可追溯：完整的决策链路记录
"""

from typing import Dict, List, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import re

from openprom.infrastructure.config import get_settings


class ControlLevel(Enum):
    """控制层级"""

    INPUT = auto()  # 输入层控制
    PROCESS = auto()  # 过程层控制
    OUTPUT = auto()  # 输出层控制
    FEEDBACK = auto()  # 反馈层控制


class ConstraintType(Enum):
    """约束类型"""

    SYNTAX = auto()  # 语法约束
    SEMANTIC = auto()  # 语义约束
    LOGICAL = auto()  # 逻辑约束
    CULTURAL = auto()  # 文化约束
    MATHEMATICAL = auto()  # 数学约束


@dataclass(frozen=True)
class ConstraintViolation:
    """约束违反记录"""

    constraint_type: ConstraintType
    field: str
    expected: Any
    actual: Any
    severity: float  # 0-1，严重程度
    message: str


@dataclass
class ControlContext:
    """控制上下文"""

    upper: str
    lower: str
    nlp_features: Dict[str, Any] = field(default_factory=dict)
    llm_raw_output: str = ""
    llm_parsed_result: Dict[str, Any] = field(default_factory=dict)
    meter_analysis: Dict[str, Any] = field(default_factory=dict)
    validation_results: List[ConstraintViolation] = field(default_factory=list)
    final_score: float = 0.0
    decision_chain: List[str] = field(default_factory=list)


# ==================== 输入层控制 ====================

# LLM 实际可能返回的"主分数"候选键（按优先级）。
# second_api_call v4.0.0 prompt 返回 technique_score / rhetoric_score；
# 早期 schema 返回 score。马鞍工程需兼容两者。
_PRIMARY_SCORE_KEYS = ("technique_score", "rhetoric_score", "score")


def _primary_score_key(result: Dict[str, Any]) -> str:
    """返回 result 中首个存在的主分数键名，若无则返回空串。"""
    for key in _PRIMARY_SCORE_KEYS:
        if key in result:
            return key
    return ""


class InputController:
    """输入层控制器

    负责对输入数据进行预处理和验证，
    确保输入符合系统要求。
    """

    # 输入长度限制
    MIN_LENGTH = 2
    MAX_LENGTH = 200

    # 允许的字符集
    ALLOWED_CHARS = re.compile(r"^[\u4e00-\u9fff\uff00-\uffef\u3000-\u303f]+$")

    def __init__(self):
        self._preprocessors: List[Callable[[str], str]] = []
        self._validators: List[Callable[[str, str], List[ConstraintViolation]]] = []
        self._register_defaults()

    def _register_defaults(self):
        """注册默认预处理器和验证器"""
        self._preprocessors.append(self._normalize_whitespace)
        self._preprocessors.append(self._remove_punctuation)

        self._validators.append(self._validate_length)
        self._validators.append(self._validate_charset)
        self._validators.append(self._validate_equality)

    def _normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        return " ".join(text.split())

    def _remove_punctuation(self, text: str) -> str:
        """移除标点符号"""
        import string

        # 保留中文标点
        chinese_punct = '，。！？；：""（）【】《》'
        translator = str.maketrans("", "", string.punctuation + chinese_punct)
        return text.translate(translator)

    def _validate_length(self, upper: str, lower: str) -> List[ConstraintViolation]:
        """验证长度约束"""
        violations = []

        for name, text in [("上联", upper), ("下联", lower)]:
            length = len(text)
            if length < self.MIN_LENGTH:
                violations.append(
                    ConstraintViolation(
                        constraint_type=ConstraintType.SYNTAX,
                        field=f"{name}.length",
                        expected=f">= {self.MIN_LENGTH}",
                        actual=length,
                        severity=1.0,
                        message=f"{name}长度不足: {length} < {self.MIN_LENGTH}",
                    )
                )
            elif length > self.MAX_LENGTH:
                violations.append(
                    ConstraintViolation(
                        constraint_type=ConstraintType.SYNTAX,
                        field=f"{name}.length",
                        expected=f"<= {self.MAX_LENGTH}",
                        actual=length,
                        severity=1.0,
                        message=f"{name}长度超限: {length} > {self.MAX_LENGTH}",
                    )
                )

        return violations

    def _validate_charset(self, upper: str, lower: str) -> List[ConstraintViolation]:
        """验证字符集约束"""
        violations = []

        for name, text in [("上联", upper), ("下联", lower)]:
            invalid_chars = []
            for i, char in enumerate(text):
                if not self.ALLOWED_CHARS.match(char):
                    invalid_chars.append((i, char))

            if invalid_chars:
                positions = [f"pos {pos}: '{char}'" for pos, char in invalid_chars[:5]]
                violations.append(
                    ConstraintViolation(
                        constraint_type=ConstraintType.SYNTAX,
                        field=f"{name}.charset",
                        expected="纯中文字符",
                        actual=f"包含非中文字符: {', '.join(positions)}",
                        severity=0.8,
                        message=f"{name}包含非中文字符",
                    )
                )

        return violations

    def _validate_equality(self, upper: str, lower: str) -> List[ConstraintViolation]:
        """验证字数相等约束"""
        violations = []

        if len(upper) != len(lower):
            violations.append(
                ConstraintViolation(
                    constraint_type=ConstraintType.SYNTAX,
                    field="length_equality",
                    expected=f"上联({len(upper)}) = 下联({len(lower)})",
                    actual=f"{len(upper)} != {len(lower)}",
                    severity=1.0,
                    message=f"字数不等: 上联{len(upper)}字，下联{len(lower)}字",
                )
            )

        return violations

    def process(self, upper: str, lower: str) -> Tuple[str, str, List[ConstraintViolation]]:
        """处理输入

        Returns:
            (处理后的上联, 处理后的下联, 约束违反列表)
        """
        # 预处理
        for preprocessor in self._preprocessors:
            upper = preprocessor(upper)
            lower = preprocessor(lower)

        # 验证
        all_violations = []
        for validator in self._validators:
            violations = validator(upper, lower)
            all_violations.extend(violations)

        return upper, lower, all_violations


# ==================== 过程层控制 ====================
class ProcessController:
    """过程层控制器

    控制LLM生成过程，通过中间干预确保输出质量。

    OpenPROM v4.3.0 的 second_api_call prompt 返回的字段是
    ``technique_score`` / ``rhetoric_score`` / ``technique_comment`` /
    ``rhetoric_comment``，而非早期版本的 ``score``。本控制器同时兼容两种
    schema：优先操作 ``technique_score``（对联评分主维度），回退 ``score``。
    """

    def __init__(self):
        self._interventions: List[Callable[[Dict[str, Any]], Dict[str, Any]]] = []
        self._register_defaults()

    def _register_defaults(self):
        """注册默认干预器"""
        self._interventions.append(self._enforce_score_range)
        self._interventions.append(self._normalize_weights)

    def _enforce_score_range(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """强制分数在有效范围内"""

        def clamp(value, min_val=0, max_val=100):
            if isinstance(value, (int, float)):
                return max(min_val, min(max_val, float(value)))
            return value

        # 主分数（兼容 technique_score / rhetoric_score / score）
        primary = _primary_score_key(result)
        if primary:
            result[primary] = clamp(result[primary])

        # 兼容早期 schema 的子分数
        for key in ["details", "意境", "修辞", "文化", "语言", "创新"]:
            if key in result and isinstance(result[key], dict):
                if "score" in result[key]:
                    result[key]["score"] = clamp(result[key]["score"])

        return result

    def _normalize_weights(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """归一化权重"""
        primary = _primary_score_key(result)
        if not primary:
            return result

        # 兼容早期 schema
        if "details" in result and isinstance(result["details"], dict):
            details = result["details"]
            scores = []
            for key, value in details.items():
                if isinstance(value, dict) and "score" in value:
                    scores.append(value["score"])

            if scores:
                avg_score = sum(scores) / len(scores)
                diff = abs(result[primary] - avg_score)
                if diff > 20:  # 差异超过20分
                    result[primary] = round(0.7 * result[primary] + 0.3 * avg_score)

        return result

    def intervene(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """执行过程干预

        Args:
            raw_result: LLM原始输出

        Returns:
            干预后的结果
        """
        result = raw_result.copy()

        for intervention in self._interventions:
            result = intervention(result)

        return result


# ==================== 输出层控制 ====================
class OutputController:
    """输出层控制器

    对最终输出进行严格验证和修正。
    """

    def __init__(self):
        self._validators: List[Callable[[ControlContext], List[ConstraintViolation]]] = []
        self._correctors: List[Callable[[ControlContext], ControlContext]] = []
        self._register_defaults()

    def _register_defaults(self):
        """注册默认验证器和修正器"""
        self._validators.append(self._validate_score_bounds)
        self._validators.append(self._validate_nlp_llm_agreement)
        self._validators.append(self._validate_meter_compliance)

        self._correctors.append(self._apply_nlp_correction)
        self._correctors.append(self._apply_meter_correction)

    def _validate_score_bounds(self, context: ControlContext) -> List[ConstraintViolation]:
        """验证分数边界"""
        violations = []
        result = context.llm_parsed_result
        primary = _primary_score_key(result)

        if primary:
            score = result[primary]
            if not (0 <= score <= 100):
                violations.append(
                    ConstraintViolation(
                        constraint_type=ConstraintType.MATHEMATICAL,
                        field=primary,
                        expected="0 <= score <= 100",
                        actual=score,
                        severity=1.0,
                        message=f"分数超出有效范围: {score}",
                    )
                )

        return violations

    def _validate_nlp_llm_agreement(self, context: ControlContext) -> List[ConstraintViolation]:
        """验证NLP与LLM结果一致性"""
        violations = []

        nlp_score = context.nlp_features.get("pos_match_rate", 0.5)
        primary = _primary_score_key(context.llm_parsed_result)
        raw_score = context.llm_parsed_result.get(primary, 50) if primary else 50
        llm_score = raw_score / 100.0

        # 计算差异
        diff = abs(nlp_score - llm_score)

        # 如果差异过大，记录警告
        if diff > 0.3:  # 30%差异阈值
            violations.append(
                ConstraintViolation(
                    constraint_type=ConstraintType.SEMANTIC,
                    field="nlp_llm_agreement",
                    expected="差异 < 0.3",
                    actual=f"差异 = {diff:.2f}",
                    severity=min(diff, 1.0),
                    message=f"NLP与LLM评分差异过大: NLP={nlp_score:.2f}, LLM={llm_score:.2f}",
                )
            )

        return violations

    def _validate_meter_compliance(self, context: ControlContext) -> List[ConstraintViolation]:
        """验证格律合规性"""
        violations = []

        meter_analysis = context.meter_analysis
        if meter_analysis.get("is_valid", True) is False:
            violations.append(
                ConstraintViolation(
                    constraint_type=ConstraintType.SYNTAX,
                    field="meter_compliance",
                    expected="格律合规",
                    actual="格律违规",
                    severity=0.7,
                    message=f"格律违规: {meter_analysis.get('errors', [])}",
                )
            )

        return violations

    def _apply_nlp_correction(self, context: ControlContext) -> ControlContext:
        """应用NLP修正：当 NLP 平仄对立率与 LLM 技法分差异过大时，加权融合。"""
        nlp_score = context.nlp_features.get("pos_match_rate", 0.5)
        llm_result = context.llm_parsed_result
        primary = _primary_score_key(llm_result)

        if primary:
            llm_score = llm_result[primary] / 100.0

            # 如果差异过大，进行融合修正
            diff = abs(nlp_score - llm_score)
            if diff > 0.3:
                # 使用加权融合
                corrected_score = 0.6 * llm_score + 0.4 * nlp_score
                original = llm_result[primary]
                llm_result[primary] = round(corrected_score * 100)
                llm_result["_nlp_correction_applied"] = True
                llm_result["_original_score"] = round(llm_score * 100)

                context.decision_chain.append(
                    f"NLP修正({primary}): {original} -> {llm_result[primary]} "
                    f"(NLP={nlp_score * 100:.1f})"
                )

        return context

    def _apply_meter_correction(self, context: ControlContext) -> ControlContext:
        """应用格律修正：格律违规时按违规数扣分。"""
        meter_analysis = context.meter_analysis
        llm_result = context.llm_parsed_result
        primary = _primary_score_key(llm_result)

        if not meter_analysis.get("is_valid", True) and primary:
            original_score = llm_result[primary]
            # 根据违规严重程度降分：warnings 即违规项
            error_count = len(
                meter_analysis.get("errors", []) or meter_analysis.get("warnings", [])
            )
            penalty = min(error_count * 5, 30)  # 每个错误扣5分，最多30分
            llm_result[primary] = max(0, original_score - penalty)
            llm_result["_meter_penalty_applied"] = True
            llm_result["_meter_penalty"] = penalty

            context.decision_chain.append(
                f"格律修正({primary}): {original_score} -> {llm_result[primary]} (违规扣{penalty}分)"
            )

        return context

    def validate(self, context: ControlContext) -> List[ConstraintViolation]:
        """执行输出验证

        Returns:
            约束违反列表
        """
        all_violations = []

        for validator in self._validators:
            violations = validator(context)
            all_violations.extend(violations)

        context.validation_results = all_violations
        return all_violations

    def correct(self, context: ControlContext) -> ControlContext:
        """执行输出修正

        Returns:
            修正后的上下文
        """
        for corrector in self._correctors:
            context = corrector(context)

        return context


# ==================== 马鞍工程主控器 ====================
class SaddleEngineering:
    """马鞍工程主控器

    整合所有控制层，提供统一的控制接口。
    """

    def __init__(self):
        self.input_controller = InputController()
        self.process_controller = ProcessController()
        self.output_controller = OutputController()

        # 控制策略配置（从 settings.yaml 读取，默认宽松）
        settings = get_settings()
        saddle_cfg = settings.get("features.saddle_engineering", {})
        self._strict_mode = saddle_cfg.get("strict_mode", False)
        self._max_violations = saddle_cfg.get("max_violations", 3)

    def execute(
        self,
        upper: str,
        lower: str,
        nlp_features: Dict[str, Any],
        llm_raw_output: str,
        llm_parsed_result: Dict[str, Any],
        meter_analysis: Dict[str, Any],
    ) -> ControlContext:
        """执行完整的马鞍工程控制流程

        Args:
            upper: 上联
            lower: 下联
            nlp_features: NLP特征
            llm_raw_output: LLM原始输出
            llm_parsed_result: LLM解析结果
            meter_analysis: 格律分析结果

        Returns:
            控制上下文（包含完整决策链）
        """
        # 1. 输入层控制
        upper, lower, input_violations = self.input_controller.process(upper, lower)

        # 创建控制上下文
        context = ControlContext(
            upper=upper,
            lower=lower,
            nlp_features=nlp_features,
            llm_raw_output=llm_raw_output,
            llm_parsed_result=llm_parsed_result.copy(),
            meter_analysis=meter_analysis,
            decision_chain=[f"输入处理: 发现{len(input_violations)}个违规"],
        )

        # 2. 过程层控制
        context.llm_parsed_result = self.process_controller.intervene(context.llm_parsed_result)
        context.decision_chain.append("过程干预: 完成")

        # 3. 输出层控制 - 验证
        output_violations = self.output_controller.validate(context)
        context.decision_chain.append(f"输出验证: 发现{len(output_violations)}个违规")

        # 4. 输出层控制 - 修正
        context = self.output_controller.correct(context)
        context.decision_chain.append("输出修正: 完成")

        # 5. 最终验证
        final_violations = self.output_controller.validate(context)

        # 6. 决策
        if self._strict_mode and len(final_violations) > self._max_violations:
            # 严格模式下，违规过多则标记为失败
            context.final_score = 0.0
            context.decision_chain.append(
                f"最终决策: 失败（违规数{len(final_violations)} > {self._max_violations}）"
            )
        else:
            # 计算最终分数：优先 technique_score/rhetoric_score，回退 score，再回退 0
            primary = _primary_score_key(context.llm_parsed_result)
            context.final_score = context.llm_parsed_result.get(primary, 0) if primary else 0
            context.decision_chain.append(f"最终决策: 通过，分数={context.final_score}")

        return context

    def get_decision_report(self, context: ControlContext) -> Dict[str, Any]:
        """生成决策报告

        Returns:
            决策报告字典
        """
        return {
            "input": {"upper": context.upper, "lower": context.lower, "length": len(context.upper)},
            "nlp_features": context.nlp_features,
            "llm_result": context.llm_parsed_result,
            "meter_analysis": context.meter_analysis,
            "violations": [
                {
                    "type": v.constraint_type.name,
                    "field": v.field,
                    "severity": v.severity,
                    "message": v.message,
                }
                for v in context.validation_results
            ],
            "decision_chain": context.decision_chain,
            "final_score": context.final_score,
        }
