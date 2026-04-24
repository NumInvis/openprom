"""PORM 终端交互界面 (Terminal User Interface)

采用素雅高级的设计风格，提供沉浸式的对联评分体验。
使用 Rich 库实现精美的文本渲染和交互效果。
"""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum, auto
import sys
import os

from porm.utils.config import load_config as _load_config
from porm.core.analyzer_interface import AnalysisResult as CoreAnalysisResult


def load_config() -> dict:
    """加载配置文件（委托给统一配置加载器）"""
    return _load_config()

from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.tree import Tree
from rich import box


class UITheme:
    """UI主题配置 - 素雅高级风格"""
    
    # 主色调 - 墨韵风格
    PRIMARY = "#2C3E50"      # 墨青
    SECONDARY = "#8E99A4"    # 银灰
    ACCENT = "#C0392B"       # 朱砂
    SUCCESS = "#27AE60"      # 竹青
    WARNING = "#F39C12"      # 琥珀
    ERROR = "#E74C3C"        # 胭脂
    
    # 背景色
    BG_DARK = "#1A1A2E"      # 深夜蓝
    BG_LIGHT = "#F8F9FA"     # 宣纸白
    
    # 文字色
    TEXT_PRIMARY = "#ECF0F1"   # 云白
    TEXT_SECONDARY = "#BDC3C7" # 雾灰
    TEXT_MUTED = "#95A5A6"     # 淡墨
    
    # 边框样式
    BORDER_STYLE = box.ROUNDED
    
    # 字体样式
    TITLE_FONT = "bold"
    SUBTITLE_FONT = "italic"
    BODY_FONT = "default"


@dataclass
class AnalysisResult(CoreAnalysisResult):
    """TUI专用分析结果（继承核心统一接口的 AnalysisResult）
    
    扩展UI展示所需的便捷字段。
    """
    duizhang_score: float = 0.0
    artistic_analysis: Dict[str, Any] = None
    impression_reason: str = ""

    def __post_init__(self):
        super().__post_init__()
        if self.duizhang_score == 0.0 and self.technique_score != 0.0:
            self.duizhang_score = self.technique_score
        if self.artistic_analysis is None:
            self.artistic_analysis = {}


class PormTUI:
    """PORM 终端用户界面"""
    
    def __init__(self):
        self.console = Console()
        self.theme = UITheme()
        self.running = True
        self.history: List[AnalysisResult] = []
        
    def clear_screen(self):
        """清屏"""
        self.console.clear()
        
    def print_header(self):
        """打印标题头"""
        title = Text()
        title.append("╭────────────────────────────────────╮\n", style=self.theme.PRIMARY)
        title.append("│  ", style=self.theme.PRIMARY)
        title.append("P O R M", style=f"bold {self.theme.ACCENT}")
        title.append("  对联评鉴系统", style=f"{self.theme.TEXT_PRIMARY}")
        title.append("     │\n", style=self.theme.PRIMARY)
        title.append("│  ", style=self.theme.PRIMARY)
        title.append("Poetic Rhythm Master", style=f"italic {self.theme.TEXT_SECONDARY}")
        title.append("          │\n", style=self.theme.PRIMARY)
        title.append("╰────────────────────────────────────╯", style=self.theme.PRIMARY)
        
        self.console.print(Align.center(title))
        self.console.print()
        
    def print_menu(self):
        """打印主菜单"""
        menu_items = [
            ("[1]", "评鉴对联", "输入上下联进行专业评鉴"),
            ("[2]", "历史记录", "查看评鉴历史"),
            ("[3]", "系统设置", "配置API参数"),
            ("[4]", "帮助说明", "查看使用指南"),
            ("[5]", "退出系统", "退出程序"),
        ]
        
        table = Table(
            show_header=False,
            box=self.theme.BORDER_STYLE,
            border_style=self.theme.SECONDARY,
            padding=(0, 2),
        )
        
        table.add_column("快捷键", style=f"bold {self.theme.ACCENT}", width=6)
        table.add_column("功能", style=f"bold {self.theme.TEXT_PRIMARY}", width=12)
        table.add_column("说明", style=self.theme.TEXT_SECONDARY)
        
        for key, func, desc in menu_items:
            table.add_row(key, func, desc)
            
        panel = Panel(
            table,
            title="[bold]主菜单[/bold]",
            border_style=self.theme.PRIMARY,
            padding=(1, 2),
        )
        
        self.console.print(panel)
        
    def get_input_couplet(self) -> tuple[str, str]:
        """获取对联输入"""
        self.console.print()
        self.console.print(
            Panel(
                "请输入对联上下联（纯中文字符，2-100字）",
                title="[bold]对联输入[/bold]",
                border_style=self.theme.PRIMARY,
            )
        )
        
        upper = Prompt.ask(
            "\n[bold]上联[/bold]",
            console=self.console
        )
        
        lower = Prompt.ask(
            "[bold]下联[/bold]",
            console=self.console
        )
        
        return upper.strip(), lower.strip()
        
    def print_analyzing(self):
        """显示分析中动画"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True,
        ) as progress:
            task = progress.add_task("正在评鉴对联...", total=None)
            import time
            time.sleep(1.5)  # 模拟分析时间
            
    def print_result(self, result: AnalysisResult):
        """打印评鉴结果"""
        self.console.print()
        
        # 对联展示
        couplet_text = Text()
        couplet_text.append(f"上联：{result.upper}\n", style=f"bold {self.theme.TEXT_PRIMARY}")
        couplet_text.append(f"下联：{result.lower}", style=f"bold {self.theme.TEXT_PRIMARY}")
        
        couplet_panel = Panel(
            couplet_text,
            title="[bold]评鉴对象[/bold]",
            border_style=self.theme.PRIMARY,
        )
        self.console.print(couplet_panel)
        
        # 总分和评级
        grade_color = self.theme.SUCCESS if result.total_score >= 80 else \
                     self.theme.WARNING if result.total_score >= 60 else self.theme.ERROR
        
        score_text = Text()
        score_text.append(f"{result.total_score:.1f}", style=f"bold {grade_color}")
        score_text.append(" 分", style=self.theme.TEXT_SECONDARY)
        score_text.append(f"  [{result.grade}]", style=f"bold {grade_color}")
        
        score_panel = Panel(
            Align.center(score_text),
            title="[bold]综合评分[/bold]",
            border_style=grade_color,
        )
        self.console.print(score_panel)
        
        # 各维度得分
        dims_table = Table(
            show_header=True,
            header_style=f"bold {self.theme.PRIMARY}",
            box=self.theme.BORDER_STYLE,
            border_style=self.theme.SECONDARY,
        )
        
        dims_table.add_column("维度", style="bold")
        dims_table.add_column("得分", justify="right")
        dims_table.add_column("权重", justify="right")
        dims_table.add_column("评价", style=self.theme.TEXT_SECONDARY)
        
        dimensions = [
            ("形式合规", result.formal_score, "30%", "平仄格律"),
            ("对仗技术", result.duizhang_score, "30%", "词性结构"),
            ("艺术表现", result.artistic_score, "30%", "意境修辞"),
            ("AI印象", result.impression_score, "10%", "整体感受"),
        ]
        
        for name, score, weight, desc in dimensions:
            score_color = self.theme.SUCCESS if score >= 0.8 else \
                         self.theme.WARNING if score >= 0.6 else self.theme.ERROR
            dims_table.add_row(
                name,
                f"{score*100:.1f}",
                weight,
                desc,
                style=score_color if score < 0.6 else None
            )
            
        dims_panel = Panel(
            dims_table,
            title="[bold]维度分析[/bold]",
            border_style=self.theme.PRIMARY,
        )
        self.console.print(dims_panel)
        
        # 艺术分析详情
        if result.artistic_analysis:
            art_tree = Tree("[bold]艺术表现分析[/bold]")
            
            for key in ["意境", "修辞", "文化", "语言", "创新"]:
                if key in result.artistic_analysis:
                    item = result.artistic_analysis[key]
                    score = item.get('score', 0)
                    comment = item.get('comment', '')
                    art_tree.add(f"[bold]{key}[/bold]: {score}分 - {comment}")
            
            if "overall_comment" in result.artistic_analysis:
                art_tree.add(f"\n[bold]总体评价[/bold]: {result.artistic_analysis['overall_comment']}")
                
            art_panel = Panel(
                art_tree,
                title="[bold]深度解析[/bold]",
                border_style=self.theme.SECONDARY,
            )
            self.console.print(art_panel)
            
        # AI印象
        if result.impression_reason:
            imp_panel = Panel(
                result.impression_reason,
                title="[bold]AI印象[/bold]",
                border_style=self.theme.ACCENT,
            )
            self.console.print(imp_panel)
            
        # 警告信息
        if result.warnings:
            warn_text = "\n".join([f"⚠ {w}" for w in result.warnings])
            warn_panel = Panel(
                warn_text,
                title="[bold]注意事项[/bold]",
                border_style=self.theme.WARNING,
            )
            self.console.print(warn_panel)
            
        self.console.print()
        
    def print_history(self):
        """打印历史记录"""
        if not self.history:
            self.console.print(
                Panel(
                    "暂无评鉴记录",
                    title="[bold]历史记录[/bold]",
                    border_style=self.theme.SECONDARY,
                )
            )
            return
            
        history_table = Table(
            show_header=True,
            header_style=f"bold {self.theme.PRIMARY}",
            box=self.theme.BORDER_STYLE,
            border_style=self.theme.SECONDARY,
        )
        
        history_table.add_column("序号", justify="center", width=4)
        history_table.add_column("上联", max_width=20)
        history_table.add_column("下联", max_width=20)
        history_table.add_column("评分", justify="right", width=6)
        history_table.add_column("评级", width=8)
        
        for i, record in enumerate(self.history[-10:], 1):  # 显示最近10条
            score_color = self.theme.SUCCESS if record.total_score >= 80 else \
                         self.theme.WARNING if record.total_score >= 60 else self.theme.ERROR
            history_table.add_row(
                str(i),
                record.upper[:20] + "..." if len(record.upper) > 20 else record.upper,
                record.lower[:20] + "..." if len(record.lower) > 20 else record.lower,
                f"{record.total_score:.1f}",
                f"[{score_color}]{record.grade}[/{score_color}]"
            )
            
        history_panel = Panel(
            history_table,
            title=f"[bold]最近{len(self.history[-10:])}条评鉴记录[/bold]",
            border_style=self.theme.PRIMARY,
        )
        self.console.print(history_panel)
        
    def print_settings(self, current_config: Dict[str, str]):
        """打印设置界面"""
        settings_table = Table(
            show_header=True,
            header_style=f"bold {self.theme.PRIMARY}",
            box=self.theme.BORDER_STYLE,
            border_style=self.theme.SECONDARY,
        )
        
        settings_table.add_column("配置项", style="bold")
        settings_table.add_column("当前值")
        settings_table.add_column("说明", style=self.theme.TEXT_SECONDARY)
        
        settings = [
            ("API密钥", "*" * 8 if current_config.get("api_key") else "未设置", "LLM API密钥"),
            ("API地址", current_config.get("base_url", "未设置"), "API基础URL"),
            ("模型", current_config.get("model", "未设置"), "LLM模型名称"),
        ]
        
        for name, value, desc in settings:
            settings_table.add_row(name, value, desc)
            
        settings_panel = Panel(
            settings_table,
            title="[bold]系统配置[/bold]",
            border_style=self.theme.PRIMARY,
        )
        self.console.print(settings_panel)
        
    def print_help(self):
        """打印帮助信息"""
        help_text = """
[bold]PORM 对联评鉴系统使用指南[/bold]

[bold]1. 评鉴对联[/bold]
   输入对联的上下联，系统将自动进行多维度评鉴。
   评鉴维度包括：形式合规、对仗技术、艺术表现、AI印象。

[bold]2. 历史记录[/bold]
   查看之前的评鉴记录，方便对比和学习。

[bold]3. 系统设置[/bold]
   配置LLM API参数，包括API密钥、地址和模型。

[bold]评分标准[/bold]
   • 优秀 (90-100分)：对仗工整，意境深远
   • 良好 (80-89分)：对仗良好，略有瑕疵
   • 及格 (60-79分)：基本合规，存在不足
   • 不及格 (0-59分)：不符合基本要求

[bold]注意事项[/bold]
   • 对联应为纯中文字符
   • 上下联字数应相等
   • 每联长度2-100字
        """
        
        help_panel = Panel(
            help_text,
            title="[bold]帮助说明[/bold]",
            border_style=self.theme.PRIMARY,
            padding=(1, 2),
        )
        self.console.print(help_panel)
        
    def print_footer(self):
        """打印底部信息"""
        footer = Text()
        footer.append("PORM v3.0 ", style=self.theme.TEXT_MUTED)
        footer.append("| ", style=self.theme.TEXT_MUTED)
        footer.append("基于NLP+LLM技术", style=self.theme.TEXT_MUTED)
        
        self.console.print(Align.center(footer))
        
    def run(self, analyzer_func: Optional[Callable] = None):
        """运行TUI主循环"""
        self.clear_screen()
        
        while self.running:
            self.print_header()
            self.print_menu()
            self.print_footer()
            
            choice = Prompt.ask(
                "\n[bold]请选择功能[/bold]",
                choices=["1", "2", "3", "4", "5"],
                default="1",
                console=self.console
            )
            
            if choice == "1":
                # 评鉴对联
                upper, lower = self.get_input_couplet()
                
                if not upper or not lower:
                    self.console.print("[red]输入不能为空[/red]")
                    continue
                    
                self.print_analyzing()
                
                # 检查是否配置了API
                if not analyzer_func:
                    error_panel = Panel(
                        "[bold red]错误：未配置LLM API[/bold red]",
                        title="[bold]配置错误[/bold]",
                        border_style=self.theme.ERROR,
                    )
                    self.console.print(error_panel)
                else:
                    try:
                        result = analyzer_func(upper, lower)
                        self.history.append(result)
                        self.print_result(result)
                    except Exception as e:
                        error_panel = Panel(
                            f"[red]评鉴失败: {e}[/red]",
                            title="[bold]错误[/bold]",
                            border_style=self.theme.ERROR,
                        )
                        self.console.print(error_panel)
                    
                input("\n按回车键继续...")
                self.clear_screen()
                
            elif choice == "2":
                # 历史记录
                self.clear_screen()
                self.print_header()
                self.print_history()
                input("\n按回车键继续...")
                self.clear_screen()
                
            elif choice == "3":
                # 系统设置
                self.clear_screen()
                self.print_header()
                # 加载配置
                config = load_config()
                self.print_settings(config)
                input("\n按回车键继续...")
                self.clear_screen()
                
            elif choice == "4":
                # 帮助说明
                self.clear_screen()
                self.print_header()
                self.print_help()
                input("\n按回车键继续...")
                self.clear_screen()
                
            elif choice == "5":
                # 退出
                self.running = False
                self.console.print("\n[italic]感谢使用 PORM，再见！[/italic]")
                

def launch_tui(analyzer_func: Optional[Callable] = None):
    """启动TUI界面
    
    Args:
        analyzer_func: 分析函数，如果为None则尝试从配置创建
        现在支持两种调用方式：
        1. 传入旧的analyze函数（向后兼容）
        2. 传入CoupletAnalyzerInterface实例（推荐）
        3. 不传参数，自动从配置创建
    """
    import os
    import json
    
    # 如果没有传入分析函数，尝试从配置创建
    if analyzer_func is None:
        config = {}
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass
        
        api_key = config.get("api_key") or os.environ.get("PORM_API_KEY")
        base_url = config.get("base_url") or os.environ.get("PORM_BASE_URL")
        model = config.get("model") or os.environ.get("PORM_MODEL")
        
        if api_key and base_url and model:
            # 使用新的统一接口（推荐）
            from porm.core.analyzer_interface import create_analyzer
            analyzer = create_analyzer(api_key, base_url, model)
            
            # 包装为兼容的函数接口
            def analyzer_func(upper, lower):
                result = analyzer.analyze(upper, lower)
                
                # 转换为TUI期望的格式
                return AnalysisResult(
                    upper=result.upper,
                    lower=result.lower,
                    total_score=result.total_score,
                    grade=result.grade,
                    formal_score=result.formal_score,
                    duizhang_score=result.technique_score,
                    artistic_score=result.artistic_score,
                    impression_score=result.impression_score,
                    warnings=result.warnings,
                    artistic_analysis=result.extra_data.get("llm_rhetoric_evaluation", {}) if result.extra_data else {},
                    impression_reason=result.comments.get("impression_comment", "")
                )
    
    tui = PormTUI()
    tui.run(analyzer_func)


def main():
    """主入口函数"""
    launch_tui()


if __name__ == "__main__":
    main()
