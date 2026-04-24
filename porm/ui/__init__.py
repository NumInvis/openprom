"""用户界面层 (User Interface Layer)

提供多种用户交互方式：
- TUI: 终端交互界面（默认）
- CLI: 命令行接口
"""

from porm.ui.tui import PormTUI, AnalysisResult, launch_tui

__all__ = [
    "PormTUI",
    "AnalysisResult",
    "launch_tui",
]
