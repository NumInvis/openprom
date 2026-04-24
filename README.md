# PORM - 对联自动评分系统

版本：4.0.0
模型：Qwen3.5-9B-Instruct

## 简介

PORM 是基于 Qwen3.5-9B-Instruct 的中文对联评分系统。

## 安装

```bash
git clone https://github.com/yourusername/porm.git
cd porm
pip install -e .
```

## 使用

### Python SDK

```python
from porm import CoupletAnalyzer

analyzer = CoupletAnalyzer(
    api_key="your-api-key",
    base_url="https://api.example.com/v1",
    model="qwen-plus"
)

result = analyzer.analyze("春风化雨", "秋月寒霜")

print(f"总分：{result.total_score}")
print(f"等级：{result.grade}")
```

### 命令行

```bash
python -m porm.main couplet "春风化雨" "秋月寒霜"
```

### TUI

```bash
python -m porm.ui.tui
```

## 配置

编辑 `config/settings.yaml`:

```yaml
model:
  model_name: "Qwen3.5-9B-Instruct"
  use_gpu: true
  
scoring:
  technique_weights:
    qwen_cosine: 0.60
    llm_technique: 0.20
    llm_rhetoric: 0.20
```

## 评分标准

| 分数 | 等级 |
|------|------|
| 90-100 | 优秀 |
| 75-89 | 良好 |
| 60-74 | 及格 |
| 0-59 | 不合格 |

## 技术栈

- Python 3.9+
- Qwen3.5-9B-Instruct
- Transformers
- PyTorch
- OpenAI SDK

## 许可证

MIT
