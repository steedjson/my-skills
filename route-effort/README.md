# Route-Effort Skill

自动根据任务复杂度路由到合适的 agent effort 级别（low/medium/high/xhigh/max）。

## 🤖 让 Claude 自动安装

复制以下指令发给 Claude Code：

```
请执行以下命令安装 route-effort skill：
bash -c "$(curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/route-effort/main/install.sh)"
```

或者直接告诉 Claude：

> "帮我安装这个 skill：https://github.com/YOUR_USERNAME/route-effort"

Claude 会自动：
1. 下载 SKILL.md 到 `~/.claude/skills/route-effort/`
2. 下载 workflow 到 `~/.claude/workflows/effort-routed-task.js`

---

## 📦 手动安装

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/route-effort/main/install.sh | bash
```

或克隆后本地安装：

```bash
git clone https://github.com/YOUR_USERNAME/route-effort.git
cd route-effort
./install.sh
```

---

## 🚀 快速开始

安装后，在 Claude Code 中运行：

```javascript
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: {task: "跨模块变更：修改缓存策略，评估影响范围"}
})
```

workflow 自动：
1. **路由**：调用 route-effort skill 评估 → 返回 `effort=xhigh`
2. **执行**：用 xhigh effort 派遣 agent 完成任务

---

## 📖 路由规则

| effort | 适用场景 | 关键词 |
|--------|---------|-------|
| `low` | 格式化、重命名、grep | 机械性、确定性 |
| `medium` | 单文件修复、代码解释 | 单文件、边界清晰 |
| `high` | 多文件功能、架构分析 | 多文件、重构、设计 |
| `xhigh` | 跨模块变更、影响评估 | **跨模块变更**、**影响N个模块** |
| `max` | 安全审计、并发分析 | 安全、并发、正确性 |

### 触发高路由的描述技巧

```
❌ "分析影响范围"           → medium（被低估）
✅ "跨模块变更：修改X，影响A/B/C模块" → xhigh
```

**规律**：描述中同时包含 **"跨模块 + 变更/修改 + 影响N个模块"** 三要素，才能可靠触发 xhigh。

---

## 🎯 使用场景

### 场景 1：简单任务（low）

```javascript
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: {task: "解释 select_related 和 prefetch_related 的区别"}
})
// 路由结果：effort=low，直接快速回答
```

### 场景 2：跨模块变更（xhigh）

```javascript
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: {
    task: "跨模块变更：修改认证中间件缓存策略，变更影响 auth、session、api 三个模块，需评估调用链风险和潜在安全问题"
  }
})
// 路由结果：effort=xhigh，深度分析后给出详细方案
```

---

## 🔧 集成到项目

### 方式 1：主 Agent 策略路由

在项目 `AGENTS.md` 中添加：

```markdown
## Task Routing Strategy

根据 effort 评估决定执行策略：

| effort | 执行策略 |
|--------|---------|
| low/medium | 主agent 直接执行 |
| high | 主agent 执行，复杂分析考虑派遣 Explore/Plan agent |
| xhigh/max | 通过 Workflow 派遣 subagent |
```

### 方式 2：自定义 Workflow 中复用

从 `effort-routed-task.js` 复制 `routeEffort()` 函数到你的 workflow：

```javascript
async function routeEffort(taskDesc) {
  const result = await agent(
    `按 route-effort 规则评估任务 effort：\n"${taskDesc}"`,
    { effort: 'medium' }
  );
  const match = result.match(/effort=(low|medium|high|xhigh|max)/);
  return match ? match[1] : 'medium';
}

// 使用
const effort = await routeEffort('你的任务');
await agent('你的任务', { effort });
```

---

## 🧪 测试

运行三个场景测试：

```bash
# 场景1：low
Workflow({scriptPath: '~/.claude/workflows/effort-routed-task.js',
         args: {task: "格式化这个文件"}})

# 场景2：medium
Workflow({scriptPath: '~/.claude/workflows/effort-routed-task.js',
         args: {task: "修复 forms.py 中参数验证 bug"}})

# 场景3：xhigh
Workflow({scriptPath: '~/.claude/workflows/effort-routed-task.js',
         args: {task: "跨模块变更：修改缓存策略，影响4个模块"}})
```

预期：`low` → `medium` → `xhigh`

---

## ❓ 常见问题

**Q: 为什么路由 agent 用 medium 而不是 low？**  
A: low effort 推理能力不足，会系统性低估复杂任务（xhigh 被评为 high）。medium 能正确评估。

**Q: 能否让主 agent 根据 effort 调整推理深度？**  
A: 主 agent 的 effort 由 session 配置决定，无法动态改变。但可以根据 effort 评估决定执行策略（直接执行 vs 派遣 subagent）。

**Q: 我的任务总是被低估怎么办？**  
A: 检查描述中是否包含触发关键词。"分析影响"→ medium，"跨模块变更 + 影响N个模块"→ xhigh。

---

## 📁 文件清单

```
route-effort/
├── README.md              — 本文件
├── install.sh             — 安装脚本（支持 curl 远程安装）
├── SKILL.md               — effort 路由规则
└── effort-routed-task.js  — 路由+执行通用 workflow
```

---

## 📝 更新日志

### v1.0.0 (2026-07-06)
- ✨ 初始版本
- 🎯 支持 low/medium/high/xhigh/max 五级路由
- 📖 包含关键词触发指南
- 🔧 修复路由 agent effort 为 medium（防止低估）
- 🚀 支持 curl 远程一键安装

---

## 📄 License

MIT

---

## 🤝 贡献

欢迎提 Issue 和 PR！

如果这个 skill 对你有帮助，请给个 ⭐️
