# TASK-006 清理弃用代码与冗余文件

## 任务描述
1. CLI (`porm/main.py`) 和 TUI (`porm/ui/tui.py`, `porm/tui_launcher.py`) 已弃用但仍存在于代码中
2. 根目录 `quick_test.py` 和 `test_web.py` 是 HTTP 烟雾测试脚本而非 pytest 测试
3. `__init__.py` 导出了弃用 TUI 相关类 (`PormTUI`, `launch_tui`)
4. `check_static.py` 是一次性调试脚本

## 技术要求
- 删除弃用 CLI 入口 `porm/main.py`
- 删除弃用 TUI 相关：`porm/ui/`, `porm/tui_launcher.py`
- 删除根目录烟雾测试脚本 `quick_test.py`, `test_web.py`
- 删除调试脚本 `check_static.py`
- 从 `__init__.py` 移除 TUI/CLI 相关导出和导入
- 清理 `porm/scripts/` 中仅服务于弃用功能的脚本

## 实现步骤
1. 确认弃用代码确实不被其他活跃代码引用
2. 删除 `porm/main.py`
3. 删除 `porm/ui/` 目录
4. 删除 `porm/tui_launcher.py`
5. 删除根目录 `quick_test.py`, `test_web.py`, `check_static.py`
6. 修改 `porm/__init__.py`：移除 TUI/CLI 导入和导出
7. 检查并清理 `porm/scripts/`

## 涉及文件
- `porm/main.py` (删除)
- `porm/ui/` (删除目录)
- `porm/tui_launcher.py` (删除)
- `quick_test.py` (删除)
- `test_web.py` (删除)
- `check_static.py` (删除)
- `porm/__init__.py` (修改)

## 验收标准
- 弃用文件已删除
- __init__.py 不再导出弃用类
- python -m porm.api 正常启动
- pytest tests/ 正常运行