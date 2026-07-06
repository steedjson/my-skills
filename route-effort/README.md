# route-effort

> Claude Code skill — 根据任务描述自动路由到合适的 agent `effort` 级别（`low`/`medium`/`high`/`xhigh`/`max`）。

**当前版本：2.3.0**

---

## 安装

```bash
# 安装（仅 SKILL.md，默认）
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash

# 安装（含 Workflow 高级用法）
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash -s -- --with-workflow
```

安装后：
- `~/.claude/skills/vlong/route-effort/SKILL.md` — skill 定义（必须）
- `~/.claude/workflows/vlong-route-effort-task.js` — Workflow 脚本（`--with-workflow` 时安装）

---

## 使用

**自动路由：**

```
Workflow({
  scriptPath: '~/.claude/workflows/vlong-route-effort-task.js',
  args: { task: '跨模块变更：修改认证中间件，评估影响范围' }
})
```

**手动指定 effort（绕过路由）：**

```
Workflow({
  scriptPath: '~/.claude/workflows/vlong-route-effort-task.js',
  args: { task: '你的任务', effort: 'xhigh' }
})
```

---

## 路由规则速查

| effort | 典型场景 |
|--------|---------|
| `low` | 格式化、重命名、grep 搜索 |
| `medium` | 单文件 bug 修复、代码解释 |
| `high` | 多文件开发、架构分析、接口设计 |
| `xhigh` | 跨模块变更、复杂 bug 根因分析 |
| `max` | 安全审计、并发竞态、微妙算法 bug |

完整规则、决策树、关键词指南见 [SKILL.md](./SKILL.md)。

---

## 升级

```bash
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash
```

---

## 已知限制

- `effort` 参数只在 Workflow 脚本的 `agent()` 中生效，不支持直接 `Agent` 工具调用
- 路由准确性对任务描述措辞敏感，模糊描述倾向被低估（保守策略）
- `effort` API 语义由 Anthropic 控制，可能随版本变更
- **模型路由不可用**：Workflow `agent()` 的 `model` 参数目前被 Claude Code 忽略，无法通过代码切换子 agent 模型

---

## 安装

```bash
# 安装（仅 SKILL.md，默认）
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash

# 安装（含 Workflow 高级用法）
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash -s -- --with-workflow
```

安装后：
- `~/.claude/skills/vlong/route-effort/SKILL.md` — skill 定义（必须）
- `~/.claude/workflows/vlong-route-effort-task.js` — Workflow 脚本（`--with-workflow` 时安装）

---

## 使用

**自动路由（effort + 模型同时路由）：**

```
Workflow({
  scriptPath: '~/.claude/workflows/vlong-route-effort-task.js',
  args: { task: '跨模块变更：修改认证中间件，评估影响范围' }
})
```

**手动指定（绕过路由）：**

```
Workflow({
  scriptPath: '~/.claude/workflows/vlong-route-effort-task.js',
  args: { task: '你的任务', effort: 'xhigh', model: 'fable' }
})
```

两者可独立 override：只指定 `model` 时 effort 仍自动路由，反之亦然。

---

## 路由规则速查

| effort | 默认模型 | 典型场景 |
|--------|----------|---------|
| `low` | `haiku` | 格式化、重命名、grep 搜索 |
| `medium` | `sonnet` | 单文件 bug 修复、代码解释 |
| `high` | `sonnet` | 多文件开发、架构分析、接口设计 |
| `xhigh` | `fable` | 跨模块变更、复杂 bug 根因分析 |
| `max` | `fable` | 安全审计、并发竞态、微妙算法 bug |

完整规则、决策树、关键词指南见 [SKILL.md](./SKILL.md)。

---

## 升级

```bash
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash
```

---

## 已知限制

- `effort` 和 `model` 参数只在 Workflow 脚本的 `agent()` 中生效，不支持直接 `Agent` 工具调用
- 路由准确性对任务描述措辞敏感，模糊描述倾向被低估（保守策略）
- `effort` / `model` API 语义由 Anthropic 控制，可能随版本变更
