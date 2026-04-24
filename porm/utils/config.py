"""项目配置加载工具（统一入口）

消除 main.py / tui.py / 测试脚本 中的重复 load_config 实现。
所有需要读取 config.json 的地方统一使用此模块。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


def get_project_root() -> Path:
    """获取项目根目录
    
    从当前文件位置向上定位到包含 config.json 的项目根。
    """
    current = Path(__file__).resolve()
    # 当前文件在 porm/utils/ 或 tests/ 下，向上查找
    for parent in [current.parent.parent.parent, current.parent.parent]:
        if (parent / "config.json").exists():
            return parent
    # 兜底：从工作目录找
    cwd = Path.cwd()
    if (cwd / "config.json").exists():
        return cwd
    return cwd


def load_config(config_path: str = None) -> Dict[str, Any]:
    """加载 API 配置文件（config.json）
    
    Args:
        config_path: 可选的显式路径，默认自动查找项目根下的 config.json
        
    Returns:
        配置字典，包含 api_key, base_url, model 等字段
    """
    if config_path is None:
        config_path = str(get_project_root() / "config.json")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}
