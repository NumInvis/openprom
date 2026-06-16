# TASK-008 Phase 3 前端改造

## 目标
实现逐字对仗分析面板、错误码映射、宣纸暖白主题细化。

## 涉及文件

### 1. frontend/styles.css
- 新增 `.tone-ping` / `.tone-ze` / `.tone-zhong` 样式
- 新增 `.word-analysis-panel` 面板样式
- 调整 light 主题配色为宣纸暖白风格

### 2. frontend/app.js
- showResult 中若 `detail.word_analysis` 存在，渲染逐字剖析面板
- API 请求错误处理：根据 error_code 显示差异化提示
- 新增 ERROR_MESSAGES 映射表

### 3. frontend/index.html
- 结果区新增 "逐字剖析" 折叠面板容器

## 验收标准
- [ ] 前端无 JS 语法错误
- [ ] 评分结果页可渲染（detail 为 None 时不崩溃）
