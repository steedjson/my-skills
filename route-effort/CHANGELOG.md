# CHANGELOG

## v2.1.0 (2026-07-06)

### 改进
- description 扩展触发范围：从"agent orchestration only"到"任何任务复杂度评估"
- 覆盖隐式场景："任务有多复杂"、"认真处理还是快速搞定"等不含 effort 关键词的请求
- 触发测试准确率：基线 38% → 100%（20/20 用例）

### 修复
- 同步版本号：SKILL.md / install.sh / README.md 统一为 2.1.0

---

## v2.0.0 (2026-07-06)

### 重大改动
- SKILL.md 全面重写为标准 skill 格式：执行指令优先，路由表次之
- SDK 示例移入 `references/sdk-examples.md`，正文大幅精简（200行→100行）
- description 新增7个明确触发场景，防止 undertriggering
- 新增具体输出示例（`[路由]`/`[完成]` 标记格式）

---

## v1.4.0 (2026-07-06)

### 改动
- SKILL.md-only 模式：基础使用不再依赖 `.js` 文件
- install.sh 默认只装 SKILL.md；`--with-workflow` 可选安装 JS
- 新增"执行流程"章节，替代 Workflow JS 的核心逻辑

---

## v1.3.0 (2026-07-06)

### 新增
- framework-agnostic 嵌入规范（可复制到任意 agent system prompt）
- Anthropic Python SDK 示例（`route_effort()` 函数）
- Anthropic TypeScript SDK 示例
- 直接文本咨询模式（零代码）

---

## v1.2.1 (2026-07-06)

### 修复
- 同步版本号（SKILL.md / install.sh / README.md）
- meta.description 去除"演示"措辞
- 已知限制基于实测数据更新（不再是未验证声明）
- description 触发意愿增强

---

## v1.2.0 (2026-07-06)

### 修复（来自 skill-creator 评测）
- 实现 `args.effort` override 逻辑（此前文档有、代码无）
- 修正 SKILL.md 内联示例：`effort: 'low'` → `effort: 'medium'`
- 删除不准确的"已知弱点"示例（实测证明不存在该弱点）
- SKILL.md 新增 effort override 文档、升级路径、已知限制章节

---

## v1.1.0 (2026-07-06)

### 修复（来自 autoplan 评审）
- `agent()` 调用缺少异常处理（critical）→ 添加 try/catch
- `install.sh` YOUR_USERNAME 占位符 → 替换为 steedjson
- 空字符串 falsy 判断 → 改为 `args?.task ?? default`
- 添加 prompt injection 隔离（`---` 分隔符）
- 移动 `phase()` 调用到主流程
- 路由失败添加诊断日志

---

## v1.0.0 (2026-07-06)

### 初始发布
- 5 级 effort 路由规则（low/medium/high/xhigh/max）
- 决策树和关键词指南
- Claude Code Workflow 实现（`vlong-route-effort-task.js`）
- 安装脚本和文档
