# TASK-001 Phase 0 前置清理

## 目标
删除项目中无引用的僵尸模块、过时缓存文件，减少认知负担和导入链污染。

## 涉及文件
- 删除：`openprom/utils/common.py`（唯一函数 `classify_similarity_level` 无外部引用）
- 删除：`openprom/utils/config.py`（功能被 `env_config.py` 完全覆盖）
- 修改：`openprom/utils/__init__.py`（移除对已删模块的引用）
- 修改：`openprom/__init__.py`（移除 `load_config` 的导入和导出）
- 删除：`openprom/core/__init__.py`（无外部引用，增加导入链）
- 删除：残留 pyc 文件（已删除模块的编译缓存）
  - `openprom/core/__pycache__/analyzer.cpython-313.pyc`
  - `openprom/core/__pycache__/analyzer_interface.cpython-313.pyc`
  - `openprom/core/__pycache__/fusion_engine.cpython-313.pyc`
  - `tests/__pycache__/test_api_full.cpython-313.pyc`
  - `tests/__pycache__/test_dual_api.cpython-313.pyc`

## 验收标准
- [ ] `grep -r "classify_similarity_level" openprom/ tests/` 无结果
- [ ] `grep -r "from openprom.utils.config" openprom/ tests/` 无结果
- [ ] `grep -r "from openprom.core import" openprom/ tests/` 无结果（验证 `core/__init__.py` 删除后无影响）
- [ ] `python -c "import openprom"` 正常执行不报错
- [ ] `python -m openprom.api` 能正常启动（到 uvicorn 监听阶段）
- [ ] `pytest tests/ --co`（仅收集测试用例）不报错
