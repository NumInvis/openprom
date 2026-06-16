"""JSON解析工具（增强版）

提供LLM响应的JSON解析功能，具备以下增强特性：
1. 多策略JSON提取：支持代码块、纯JSON、混合文本
2. 自动修复：处理单引号、尾逗号、注释等常见LLM输出问题
3. 结构验证：确保必需字段存在，缺失时使用默认值
4. 详细错误报告：解析失败时提供可操作的错误信息
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class JSONParseError(Exception):
    """JSON解析异常"""
    def __init__(self, message: str, raw_content: str = "", fix_attempts: List[str] = None):
        self.message = message
        self.raw_content = raw_content[:500] if raw_content else ""
        self.fix_attempts = fix_attempts or []
        super().__init__(self.message)


def _extract_json_string(content: str) -> Optional[str]:
    """从LLM响应中提取JSON字符串
    
    按优先级尝试多种提取策略：
    1. ```json ... ``` 代码块
    2. ``` ... ``` 代码块（无语言标记）
    3. 最外层 { ... } 对象（贪婪匹配，处理嵌套）
    """
    if not content or not content.strip():
        return None
    
    # 策略1：markdown代码块 - json标记
    code_block_match = re.search(
        r'```(?:json)?\s*\n?(.*?)\n?\s*```', 
        content, 
        re.DOTALL | re.IGNORECASE
    )
    if code_block_match:
        extracted = code_block_match.group(1).strip()
        if extracted.startswith('{') or extracted.startswith('['):
            logger.debug("JSON提取成功: markdown代码块(json)")
            return extracted
    
    # 策略2：markdown代码块 - 无标记
    code_block_match_generic = re.search(
        r'```\s*\n?(.*?)\n?\s*```', 
        content, 
        re.DOTALL
    )
    if code_block_match_generic:
        extracted = code_block_match_generic.group(1).strip()
        if extracted.startswith('{') or extracted.startswith('['):
            logger.debug("JSON提取成功: markdown代码块(通用)")
            return extracted
    
    # 策略3：智能括号匹配 - 找到最外层的完整JSON对象/数组
    # 使用栈来正确处理嵌套的 {} 和 []
    brace_stack = []  # stores (char, pos)
    
    for i, char in enumerate(content):
        if char in '{[':
            brace_stack.append((char, i))
        elif char in '}]':
            if brace_stack:
                last_char, start = brace_stack[-1]
                expected = '}' if last_char == '{' else ']'
                if char == expected:
                    brace_stack.pop()
                    if not brace_stack:
                        extracted = content[start:i+1]
                        logger.debug(f"JSON提取成功: 括号匹配 (pos {start}-{i})")
                        return extracted
                else:
                    # 不匹配，丢弃整个当前层级
                    brace_stack = []
    
    # 策略4：最后的尝试 - 简单正则（仅当内容较短时）
    if len(content) < 2000:
        simple_match = re.search(r'\{[\s\S]*\}', content)
        if simple_match:
            logger.debug("JSON提取成功: 简单正则回退")
            return simple_match.group()
    
    return None


def _repair_json_string(json_str: str) -> tuple:
    """修复常见的LLM输出JSON问题
    
    Returns:
        (repaired_str, applied_fixes列表)
    """
    fixes_applied = []
    repaired = json_str.strip()
    
    # 修复1：移除BOM和特殊前缀字符
    if repaired and repaired[0] in ('\ufeff', '\ufffe'):
        repaired = repaired[1:]
        fixes_applied.append("移除BOM")
    
    # 修复2：单引号替换为双引号
    # 当单引号数量明显多于双引号时，认为是单引号 JSON
    sq_count = repaired.count("'")
    dq_count = repaired.count('"')
    if sq_count > 0 and sq_count >= dq_count:
        repaired = _convert_single_quotes(repaired)
        fixes_applied.append("单引号转双引号")
    
    # 修复3：移除JavaScript风格的尾部逗号
    # 如 {"a": 1, "b": 2,} → {"a": 1, "b": 2}
    repaired, comma_fixes = _fix_trailing_commas(repaired)
    fixes_applied.extend(comma_fixes)
    
    # 修复4：移除注释（// 和 /* */ 风格）
    repaired, comment_fixes = _remove_comments(repaired)
    fixes_applied.extend(comment_fixes)
    
    # 修复5：修复未引用的键名（如 {key: "value"} → {"key": "value"}）
    repaired, key_fixes = _fix_unquoted_keys(repaired)
    fixes_applied.extend(key_fixes)
    
    # 修复6：处理None/True/False（Python风格→JSON风格）
    python_json_map = [
        (r'\bNone\b', 'null'),
        (r'\bTrue\b', 'true'),
        (r'\bFalse\b', 'false'),
    ]
    for pattern, replacement in python_json_map:
        new_repaired = re.sub(pattern, replacement, repaired)
        if new_repaired != repaired:
            fixes_applied.append(f"{pattern} → {replacement}")
            repaired = new_repaired
    
    return repaired, fixes_applied


def _convert_single_quotes(s: str) -> str:
    """智能转换单引号为双引号
    
    策略：如果整个字符串被单引号包裹，直接去除首尾单引号；
    否则，仅替换作为字符串边界的单引号（保守策略）。
    """
    s = s.strip()
    # 如果被单引号整体包裹，直接去除
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    
    # 否则使用状态机，但只替换字符串边界的单引号
    result = []
    in_string = False
    string_delim = None
    escape_next = False
    
    for char in s:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        
        if char == '\\':
            result.append(char)
            escape_next = True
            continue
        
        if char in ('"', "'"):
            if not in_string:
                in_string = True
                string_delim = char
                result.append('"')
                continue
            elif char == string_delim:
                in_string = False
                string_delim = None
                result.append('"')
                continue
            else:
                # 另一种引号在字符串内部，原样保留
                result.append(char)
                continue
        
        result.append(char)
    
    return ''.join(result)


def _fix_trailing_commas(s: str) -> tuple:
    """修复尾部逗号"""
    fixes = []
    
    # 对象中的尾部逗号: ,"}" 或 , whitespace }
    new_s, count = re.subn(r',(\s*[}\]])', r'\1', s)
    if count > 0:
        fixes.append(f"移除{count}个尾部逗号")
    
    return new_s, fixes


def _remove_comments(s: str) -> tuple:
    """移除JS风格注释"""
    fixes = []
    
    # 单行注释
    new_s, count = re.subn(r'//[^\n]*', '', s)
    if count > 0:
        fixes.append(f"移除{count}行单行注释")
    
    # 多行注释
    new_s, count2 = re.subn(r'/\*.*?\*/', '', new_s, flags=re.DOTALL)
    if count2 > 0:
        fixes.append(f"移除{count2}块多行注释")
    
    return new_s, fixes


def _fix_unquoted_keys(s: str) -> tuple:
    """修复未引用的键名（保守策略）"""
    fixes = []
    
    # 匹配: 字母/下划线/中文开头 + 字母数字下划线中文 + 冒号
    # 只在对象开始或逗号后匹配
    pattern = r'(?<=[{\s,])([a-zA-Z_\u4e00-\u9fff][a-zA-Z0-9_\u4e00-\u9fff]*)(\s*:)'
    
    def replace_key(m):
        key = m.group(1)
        if key.lower() in ('true', 'false', 'null'):
            return m.group(0)
        return f'"{key}"{m.group(2)}'
    
    new_s, count = re.subn(pattern, replace_key, s)
    if count > 0:
        fixes.append(f"修复{count}个未引用键名")
    
    return new_s, fixes


def validate_and_fill_defaults(
    data: Dict[str, Any],
    required_fields: Dict[str, Any]
) -> Dict[str, Any]:
    """验证并填充默认值
    
    Args:
        data: 解析后的JSON数据
        required_fields: 必需字段及其默认值 {field_name: default_value}
        
    Returns:
        验证后的数据（缺失字段已填充默认值）
    """
    validated = dict(data)
    missing_fields = []
    
    for field_name, default_value in required_fields.items():
        if field_name not in validated or validated[field_name] is None:
            validated[field_name] = default_value
            missing_fields.append(field_name)
            logger.warning(f"JSON字段缺失，使用默认值: {field_name} = {default_value}")
    
    if missing_fields:
        logger.info(f"JSON验证完成，补充了 {len(missing_fields)} 个缺失字段: {missing_fields}")
    
    return validated


def parse_llm_json_response(
    content: str,
    required_fields: Optional[Dict[str, Any]] = None,
    max_repair_attempts: int = 3
) -> Dict[str, Any]:
    """解析LLM返回的JSON响应（增强版）
    
    Args:
        content: LLM原始响应文本
        required_fields: 必需字段及默认值，如 {"score": 0, "reason": ""}
        max_repair_attempts: 最大修复尝试次数
        
    Returns:
        解析后的字典
        
    Raises:
        JSONParseError: 解析彻底失败时抛出
    """
    if not content or not content.strip():
        raise JSONParseError("响应内容为空", content)
    
    if required_fields is None:
        required_fields = {}
    
    # 步骤1：提取JSON字符串
    json_str = _extract_json_string(content)
    
    if json_str is None:
        raise JSONParseError(
            f"无法从响应中提取JSON。响应长度: {len(content)}",
            content
        )
    
    # 步骤2：尝试直接解析
    fix_attempts = []
    
    for attempt in range(max_repair_attempts + 1):
        try:
            if attempt > 0:
                json_str, round_fixes = _repair_json_string(json_str)
                fix_attempts.extend(round_fixes)
                
                if not round_fixes:
                    # 没有更多可修复的问题
                    break
            
            data = json.loads(json_str)
            
            # 步骤3：验证和填充默认值
            if required_fields:
                data = validate_and_fill_defaults(data, required_fields)
            
            if fix_attempts:
                logger.info(f"JSON解析成功（经过{len(fix_attempts)}次修复）: {fix_attempts[:5]}")
            
            return data
            
        except json.JSONDecodeError as e:
            if attempt == max_repair_attempts:
                error_detail = f"JSON解析失败: {e}"
                if fix_attempts:
                    error_detail += f" | 已尝试修复: {fix_attempts}"
                raise JSONParseError(error_detail, json_str, fix_attempts)
            continue
    
    raise JSONParseError("JSON解析失败: 达到最大重试次数", json_str, fix_attempts)


def safe_parse_llm_response(
    content: str,
    required_fields: Optional[Dict[str, Any]] = None,
    fallback: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """安全解析LLM响应（永不抛出异常）
    
    当解析失败时返回fallback值。
    
    Args:
        content: LLM原始响应
        required_fields: 必需字段及默认值
        fallback: 解析完全失败时的回退值
        
    Returns:
        解析结果或fallback值
    """
    try:
        return parse_llm_json_response(content, required_fields)
    except JSONParseError as e:
        logger.error(f"安全解析降级: {e.message}")
        
        if fallback is not None:
            result = dict(fallback)
        else:
            result = {"score": 50, "reason": "解析失败，使用默认值", "error": str(e)}
        
        if required_fields:
            for field, default in required_fields.items():
                if field not in result:
                    result[field] = default
        
        return result
