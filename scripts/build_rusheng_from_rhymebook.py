#!/usr/bin/env python3
"""从项目内置的平水韵数据生成入声字表。

平水韵共 106 部，其中入声 17 部（屋、沃、觉、质、物、月、曷、黠、
屑、药、陌、锡、职、缉、合、叶、洽）。本脚本读取
`openprom/data/rhymebooks.json` 中平水韵第二组的最后 17 个韵部，
提取所有入声字，去重排序后写入 `openprom/data/rusheng.json`。

数据来源：项目内置韵书数据库（平水韵），非 AI 生成或穷举。
"""

import json
import os


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RHYMEBOOKS_PATH = os.path.join(PROJECT_ROOT, "openprom", "data", "rhymebooks.json")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "openprom", "data", "rusheng.json")
# 平水韵入声韵部固定为 17 个
PING_SHUI_RUSHENG_GROUP_COUNT = 17


def build_rusheng_set(rhymebooks: dict) -> set:
    """从平水韵入声韵部提取入声字集合。"""
    ping_shui = rhymebooks.get("平水韵")
    if not isinstance(ping_shui, list) or len(ping_shui) < 2:
        raise ValueError("平水韵数据格式异常")

    shang_qu_ru_groups = ping_shui[1]
    if len(shang_qu_ru_groups) < PING_SHUI_RUSHENG_GROUP_COUNT:
        raise ValueError("平水韵上/去/入声分组数量不足")

    rusheng_groups = shang_qu_ru_groups[-PING_SHUI_RUSHENG_GROUP_COUNT:]
    rusheng_chars = set()
    for group in rusheng_groups:
        if not isinstance(group, str):
            raise ValueError("韵部应为字符串")
        rusheng_chars.update(group)

    # 过滤非汉字字符（如控制字符、标点）
    rusheng_chars = {ch for ch in rusheng_chars if "\u4e00" <= ch <= "\u9fff"}
    return rusheng_chars


def main() -> None:
    with open(RHYMEBOOKS_PATH, "r", encoding="utf-8") as f:
        rhymebooks = json.load(f)

    rusheng_chars = build_rusheng_set(rhymebooks)
    output = sorted(rusheng_chars)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"已生成 {OUTPUT_PATH}，共 {len(output)} 个入声字")


if __name__ == "__main__":
    main()
