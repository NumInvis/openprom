#!/usr/bin/env python3
"""测试对联评鉴"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from porm import CoupletAnalyzer
from porm.utils.config import load_config

config = load_config()

print('正在初始化分析器（首次会下载BERT模型到本地）...')
analyzer = CoupletAnalyzer(config['api_key'], config['base_url'], config['model'])

print('\n分析对联：')
print('上联：几孤风月')
print('下联：屡变星霜')
print('\n正在评鉴...')

result = analyzer.analyze('几孤风月', '屡变星霜')

print(f'\n=== 评鉴结果 ===')
print(f'总分：{result.total_score} 分')
print(f'评级：{result.grade}')
print(f'\n形式合规：{result.formal_score * 100:.1f} 分')
print(f'技法分析：{result.technique_score * 100:.1f} 分')
print(f'艺术表现：{result.artistic_score * 100:.1f} 分')
print(f'AI印象：{result.impression_score * 100:.1f} 分')
print(f'\n技法评语：{result.technique_comment[:200]}...')
print(f'\n艺术评语：{result.artistic_comment[:200]}...')
print(f'\n总评：{result.overall_comment}')
