# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

**vlong** — 个人 Claude Code skills 集合包。每个 skill 是一个独立子目录，通过包级安装器统一管理。

GitHub repo: `steedjson/my-skills`（安装后以 `vlong` 为包名）

## 包结构

```
my-skills/              ← vlong 包根目录
├── install.sh              ← 包级安装器（安装一个或全部 skill）
├── skills.json             ← 包清单（skill 列表、版本、文件）
├── shared/
│   └── install_skill.sh    ← 单 skill 安装逻辑（共享函数库）
├── route-effort/           ← skill 实体
│   ├── SKILL.md
│   ├── install.sh          ← 薄壳，代理到根 install.sh
│   ├── references/
│   ├── scripts/            ← SkillOpt 脚本
│   └── skill-opt/          ← 训练数据（--with-skill-opt 时创建）
└── CLAUDE.md
```

## 安装方式

```bash
# 安装全部 skill
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash

# 安装指定 skill
curl -fsSL .../install.sh | bash -s -- route-effort

# 带训练支持
curl -fsSL .../install.sh | bash -s -- route-effort --with-skill-opt

# 或直接用 skill 的入口
curl -fsSL .../route-effort/install.sh | bash
```

升级：重新运行安装命令，覆盖安装即可。

## 新增 skill 规范

每个 skill 目录最少包含：

| 文件 | 必须 | 说明 |
|------|------|------|
| `SKILL.md` | ✅ | skill 定义（frontmatter: name, version, description） |
| `install.sh` | ✅ | 薄壳，代理到根 install.sh |
| `README.md` | ✅ | 安装说明 + 快速参考 |
| `references/` | 可选 | SDK 示例、参考文档 |
| `scripts/` | 可选 | SkillOpt 脚本（log_usage.py 等） |

新增 skill 时同步更新 `skills.json`。

## route-effort skill

路由任务描述到合适的 agent `effort` 级别（`low`/`medium`/`high`/`xhigh`/`max`）。

关键约束：`effort` 参数只在 Workflow 脚本的 `agent()` 中生效，直接 `Agent` 工具调用无效。

触发测试：20/20 = 100%（v2.1.0，触发范围覆盖隐式复杂度评估场景）

## 常用命令

```bash
# 安装 route-effort
./install.sh route-effort

# 安装并启用训练支持
./install.sh route-effort --with-skill-opt

# 本地升级（符号链接安装后）
git pull

# 测试日志
cat ~/.claude/skills/route-effort/skill-opt/route-effort-usage.jsonl
```
