# TASK-003 Phase 1 前端止血

## 目标
修复前端 P0 阻断问题：BERT 残留、假进度欺骗、XSS 漏洞、session 隔离、默认主题。

## 涉及文件与改动点

### 1. frontend/index.html
- `data-theme="dark"` → `"light"`（宣纸暖白默认）
- 删除 `bertScore` DOM 元素及 BERT 语义相似度标签（或替换为 LLM 分析描述）

### 2. frontend/app.js
- 删除 `bertScore` DOM 引用
- 删除 `data.qwen_analysis.cosine_similarity` 引用
- `API.analyze` 请求头添加 `X-Session-ID`（从 localStorage 读取或生成 UUID）
- `showResult` 中四维度分数去掉 `*100`（后端 TASK-002 已统一为 0-100）
- `showResult` 中 `warningsList.innerHTML` 改为 `createElement + textContent` 防 XSS
- 删除假进度 `setInterval`，改为：请求前 `setLoadingStep(0)`，收到响应后 `setLoadingStep(3)`
- 加载步骤文案 "融合计算中..." → "总评生成中..."

## 验收标准
- [ ] 页面默认主题为 light（暖白）
- [ ] 前端无 BERT 相关 DOM 和 JS 引用
- [ ] API 请求携带 `X-Session-ID` header
- [ ] `warningsList` 使用 `textContent` 渲染，不执行 HTML
- [ ] 无 `setInterval` 假进度动画
- [ ] `showResult` 中四维度分数直接渲染，不 `*100`
