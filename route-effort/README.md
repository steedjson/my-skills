# route-effort

> Claude Code skill — 根据任务描述自动路由到合适的 agent `effort` 级别（`low`/`medium`/`high`/`xhigh`/`max`）。

**当前版本：2.1.0**

---

## 安装

### 本地安装（仅 SKILL.md，推荐）

```bash
./install.sh
```

### 本地安装（含 Workflow 高级用法）

```bash
./install.sh --with-workflow
```

### 远程安装

```bash
# 仅 SKILL.md
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash

# 含 Workflow
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash -s -- --with-workflow
```

安装后：
- `~/.claude/skills/route-effort/SKILL.md` — skill 定义（必须）
- `~/.claude/workflows/effort-routed-task.js` — Workflow 脚本（`--with-workflow` 时安装）

---

## 使用

**自动路由：**

```
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
  args: { task: '跨模块变更：修改认证中间件，评估影响范围' }
})
```

**手动指定 effort（绕过路由）：**

```
Workflow({
  scriptPath: '~/.claude/workflows/effort-routed-task.js',
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
./install.sh   # 本地
# 或
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/route-effort/install.sh | bash
```

---

## 已知限制

- `effort` 参数只在 Workflow 脚本的 `agent()` 中生效，不支持直接 `Agent` 工具调用
- 路由准确性对任务描述措辞敏感，模糊描述倾向被低估（保守策略）
- `effort` API 语义由 Anthropic 控制，可能随版本变更
