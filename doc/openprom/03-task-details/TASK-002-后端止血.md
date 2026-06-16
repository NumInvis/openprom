# TASK-002 Phase 1 后端止血

## 目标
修复后端 P0 致命缺陷：严格模式杀死所有结果、分数单位混乱、formal_score=pingze_score、CORS 安全隐患、数据库模块级实例化。

## 涉及文件与改动点

### 1. openprom/core/saddle_engineering.py
- `SaddleEngineering.__init__` 中 `_strict_mode` 和 `_max_violations` 从 `settings.yaml` 读取
- 默认 `strict_mode=false`、`max_violations=3`
- 区分 HARD_REJECT（致命错误如字数不等）和 SOFT_CORRECT（参考性约束如 NLP 差异）

### 2. openprom/core/base_analyzer.py
- `analyze_formal()` 中 `formal_score` 独立计算：`formal_score = 0.5*length_match + 0.3*pingze + 0.2*structure`
- `structure` 暂时返回 1.0（占位，后续由词性匹配实现）
- 字数不等时返回 `(0.0, 0.0, ["字数不等"])`

### 3. openprom/core/dual_api_scorer.py
- 确认 `normalize_score(..., max_score=100)` 将 LLM 返回转换为 0-1
- `_score_to_response()` 中四维度分数统一乘以 100 后输出
- `calculate_total_score()` 返回 0-100（已有 `*100`）

### 4. openprom/api.py
- CORS `allow_origins` 改为从 `OPENPROM_CORS_ORIGINS` 环境变量读取，默认 `["*"]`（仅 dev）
- 生产环境禁止 `*` + `credentials=True` 组合
- `_score_to_response()` 中四维度分数 `*100`
- `history` 端点读取 `X-Session-ID` header 过滤

### 5. openprom/infrastructure/database.py
- `CoupletAnalysis` 新增 `session_id = Column(String(64), nullable=True, index=True)`
- 删除模块级 `db_manager = DatabaseManager()`
- 新增 `get_db_manager()` 工厂函数（`@lru_cache(maxsize=1)`）
- `api.py` 中替换 `db_manager` 导入为 `get_db_manager()`

## 验收标准
- [ ] `saddle_engineering` 严格模式读取配置，输入有轻微平仄差异的对联返回非 0 分
- [ ] `base_analyzer.analyze_formal("春风", "秋雨")` 返回的 formal_score ≠ pingze_score
- [ ] API 响应中 `formal_score` / `technique_score` / `artistic_score` / `impression_score` 均在 0-100 范围
- [ ] CORS 配置按环境变量切换
- [ ] `pytest tests/test_integration.py` 8 个测试全部通过
- [ ] `python -c "import openprom; from openprom.infrastructure.database import get_db_manager; print('ok')"` 正常
