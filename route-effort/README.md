# route-effort

> Claude Code skill — 根据任务描述自动路由到合适的 agent `effort` 级别（`low`/`medium`/`high`/`xhigh`/`max`）。

**当前版本：2.4.0**

---

## 安装

**一键安装**（推荐）：

```bash
# 基础安装
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash -s -- route-effort

# 完整安装（含 Workflow + SkillOpt）
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash -s -- route-effort --with-workflow --with-skill-opt
```

**安装原理**：
- 自动检测环境：有 `git` → clone 仓库，无 `git` → 下载 tarball
- **仅需一次网络请求**，无 GitHub API 限流（429）问题
- 临时目录自动清理（`trap`）
- 安装到 `~/.claude/skills/vlong/route-effort/`

**手动安装**（从本地仓库）：

```bash
git clone https://github.com/steedjson/my-skills.git
cd my-skills
./install.sh route-effort --with-workflow --with-skill-opt
```

**安装后文件**：
- `~/.claude/skills/vlong/route-effort/SKILL.md` — skill 定义（必须）
- `~/.claude/skills/vlong/route-effort/scripts/` — SkillOpt 训练脚本
- `~/.claude/workflows/vlong-route-effort-task.js` — Workflow 脚本（`--with-workflow`）

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

**SkillOpt 训练验证：测试集准确率 80%，Soft 评分 0.950**

| effort | 默认模型 | 典型场景 |
|--------|----------|---------|
| `low` | `haiku` | 格式化、重命名、文本替换、添加注释 |
| `medium` | `sonnet` | 单文件 bug 修复、代码解释 |
| `high` | `sonnet` | 多文件开发、架构分析、接口设计 |
| `xhigh` | `fable` | 跨模块重构、根因分析、影响评估 |
| `max` | `fable` | 安全审计、并发 bug、关键算法修复 |

完整规则、决策树、关键词指南见 [SKILL.md](./SKILL.md)。

**训练方法**：基于 50 个真实任务样本（40 train + 5 val + 5 test）通过 SkillOpt 系统验证规则有效性。详见 [SkillOpt 训练报告](../skillopt-training-summary.md)。

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
