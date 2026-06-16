#!/usr/bin/env python3
"""OpenPROM 配置设置脚本

自动配置 API 密钥、模型和站点信息。
从 scripts/ 目录运行时，config.json 会写入项目根目录。
"""

import json
import os
from pathlib import Path


def setup_config():
    """设置配置文件"""
    print("OpenPROM 配置设置")
    print("=" * 50)
    
    api_key = os.getenv("OPENPROM_API_KEY", "")
    if not api_key:
        api_key = input("请输入 API 密钥 (或按回车使用环境变量): ").strip()
    
    base_url = input("API Base URL [https://proxy.pieixan.icu/v1]: ").strip()
    if not base_url:
        base_url = "https://proxy.pieixan.icu/v1"
    
    model = input("模型名称 [Qwen3.5-9B-Instruct]: ").strip()
    if not model:
        model = "Qwen3.5-9B-Instruct"
    
    config = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "_note": "建议将 API 密钥设置在 .env 文件中或使用 OPENPROM_API_KEY 环境变量"
    }
    
    config_path = Path(__file__).resolve().parent.parent / "config.json"
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    
    print(f"\n✓ 配置文件已保存：{config_path}")
    print(f"  - API 密钥：{api_key[:20] + '...' if api_key else '(使用环境变量)'}")
    print(f"  - 模型：{model}")
    print(f"  - Base URL: {base_url}")
    print("\n提示：建议将敏感信息设置在 .env 文件中")
    print("运行：python -m openprom.api 启动 API 服务")


if __name__ == "__main__":
    setup_config()
