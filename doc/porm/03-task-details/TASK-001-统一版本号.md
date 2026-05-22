# TASK-001 统一版本号

## 任务描述
项目中版本号不一致：`__init__.py` 写 3.1.0，`pyproject.toml` 写 4.0.0，`api.py` docstring 写 4.1.0，api.py FastAPI(version=) 写 4.1.0，health/root 端点写 4.2.0，README 写 4.2.0。统一到 4.2.0。

## 技术要求
- 修改 `porm/__init__.py` 的 `__version__` 为 `"4.2.0"`
- 修改 `porm/__init__.py` docstring 版本描述
- 修改 `pyproject.toml` 的 version 为 `"4.2.0"`
- 修改 `porm/api.py` docstring 版本描述为 4.2.0
- 修改 `porm/api.py` FastAPI(version=) 为 `"4.2.0"`
- `config/settings.yaml` 版本注释同步

## 实现步骤
1. 修改 `porm/__init__.py`: `__version__ = "4.2.0"`, docstring 更新
2. 修改 `pyproject.toml`: version = "4.2.0"
3. 修改 `porm/api.py`: docstring 和 FastAPI(version="4.2.0")
4. 修改 `config/settings.yaml`: 版本注释

## 涉及文件
- `porm/__init__.py`
- `pyproject.toml`
- `porm/api.py`
- `config/settings.yaml`

## 验收标准
- 所有文件版本号统一为 4.2.0
- 无遗漏的硬编码版本号