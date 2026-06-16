# TASK-005 Phase 2 测试重建

## 目标
将测试架构从"脚本式"重建为"pytest 标准式"，支持 CI 运行。

## 涉及文件与改动点

### 1. tests/conftest.py（新增）
- 提供 `client` fixture（`TestClient(app)`）
- 提供 `db` fixture（内存 SQLite，隔离测试数据）

### 2. tests/test_integration.py（重写）
- 所有 `print` 改为 `assert`
- 删除 `main()` 和 `if __name__ == '__main__':`
- 删除 `return True`
- `test_database` 使用 `:memory:` 数据库或验证统计信息结构

### 3. tests/test_couplet.py（改写）
- 改为 pytest 格式（`def test_xxx():`）
- 添加 `@pytest.mark.skipif(not os.getenv("OPENPROM_API_KEY"), reason="需要 API Key")`
- 移除 `sys.path.insert` 和脚本式入口

### 4. tests/test_web_interface.py（修改）
- `headless=False` → `headless=True`
- 所有 `time.sleep(N)` 替换为 `page.wait_for_selector(...)` 或 `expect(...)`
- 删除 `if __name__ == '__main__':`

## 验收标准
- [ ] `pytest tests/ --co` 能收集到所有测试用例（无 import error）
- [ ] `pytest tests/test_integration.py -v` 8 个测试全部通过（assert 方式）
- [ ] `pytest tests/test_couplet.py -v` 正确 skip（无 API Key 时）或 pass
- [ ] `pytest tests/test_web_interface.py -v` 正确 skip（无服务器时）或 pass
- [ ] 无 `PytestReturnNotNoneWarning`
