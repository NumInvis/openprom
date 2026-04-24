#!/usr/bin/env python3
"""PORM TUI 启动器

提供简单的方式启动终端交互界面。
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from porm.ui import launch_tui


def main():
    """主函数"""
    try:
        launch_tui()
    except KeyboardInterrupt:
        print("\n\n感谢使用 PORM，再见！")
        sys.exit(0)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
