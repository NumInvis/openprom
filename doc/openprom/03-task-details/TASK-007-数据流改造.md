# TASK-007 Phase 3 数据流改造

## 目标
透传 LLM 返回的 word_analysis，API 响应支持 detail 字段。

## 涉及文件与改动点

### 1. openprom/core/dual_api_scorer.py
- `DualAPIScore` 添加 `word_analysis` 字段
- `analyze()` 中从 `second_result` 提取 `word_analysis` 并保存

### 2. openprom/api.py
- `_score_to_response()` 中透传 `detail` 字段（包含 word_analysis，Optional）

## 验收标准
- [ ] `DualAPIScore` 包含 `word_analysis` 字段
- [ ] `_score_to_response` 返回的 `CoupletResponse.detail` 非 None 时包含 `word_analysis`
- [ ] `pytest tests/test_integration.py` 全部通过
