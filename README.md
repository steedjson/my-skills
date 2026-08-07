# vlong's Claude Code Skills

个人 Agent Skills 与 Codex 插件源码集合。

## Skills 列表

### [codexradar-model-advisor](./codexradar-model-advisor/)

读取 CodexRadar 当前实测数据与 15 天社区评分历史，为 OpenAI Codex 模型和 reasoning effort 提供质量、速度、成本建议。仅推荐当前有实测数据的组合，支持 Codex、Claude Code 和其他 Agent Skills 兼容宿主。

### [model-delegate](./model-delegate/)

使用 Codex App 原生顶层任务建立轻量规划与执行分工。规划任务保留需求、架构、审查和验收职责；用户确认模型与 effort 后创建可见执行任务，并通过正式任务 ID 等待、处理阻塞和继续派发。

### [ccswitchmulti-reasoning-tier-repair](./ccswitchmulti-reasoning-tier-repair/)

读取实时 CCSwitchMulti 与 Codex 配置，检查并修复已核实模型的 `low`、`medium`、`high`、`xhigh`、`max`、`ultra` reasoning 档位，并检测已安装 CCSwitchMulti 运行时是否真的支持目标档位。支持检查、预览、备份和写入后 TOML/JSON/数据库验证；未知模型保留原值并报告。

### [chatgpt-codex-history-repair](./chatgpt-codex-history-repair/)

只处理 ChatGPT.app 内置 Codex 的本地历史可见性：先定位 active SQLite，核对 session JSONL、索引和项目提示，再做 dry-run。默认只读，写入前备份并要求明确确认；不删除会话正文，也不做 provider 迁移。

### [custom-image-gen](./openai/custom-image-gen/)

通过 `auth.json` 和当前 Codex provider 配置解析自定义图片生成端点与凭据，再复用系统 `imagegen` Skill 和 CLI。仅负责 provider 适配，不复制系统图片生成工作流。

### [django-api-change](./django-api-change/) *(project: wework)*

在 wework 项目中实现、调试或审查 Django API 与 Service 变更。涵盖路由、视图、参数 Schema、Service、模型、迁移、权限、租户隔离、事务、软删除、导出和 API 测试场景。遵循 View → Form/Schema → Service → Model 分层约定。

## Codex 插件

`openai/` 可包含需要构建、测试、安装和显式信任 hook 的 Codex 插件运行时。插件不是独立 Agent Skill，不登记到 `skills.json`。

### [openwolf-codegraph](./openai/openwolf-codegraph/)

在用户级统一接入 Codex 生命周期事件。仅当仓库存在 `.wolf/` 或 `.codegraph/` 时启用：转发 OpenWolf 本地 hook，并注入 CodeGraph 优先导航规则。

完整安装 / 使用 / 验证 / 卸载说明见 [`openai/openwolf-codegraph/README.md`](./openai/openwolf-codegraph/README.md)。

---

## 安装

复制 skill 目录下的 `SKILL.md` 到 Claude Code skills 路径：

```bash
mkdir -p ~/.claude/skills/codexradar-model-advisor
cp codexradar-model-advisor/SKILL.md ~/.claude/skills/codexradar-model-advisor/SKILL.md

mkdir -p ~/.claude/skills/model-delegate
cp model-delegate/SKILL.md ~/.claude/skills/model-delegate/SKILL.md

mkdir -p ~/.claude/skills/ccswitchmulti-reasoning-tier-repair
cp -R ccswitchmulti-reasoning-tier-repair/. ~/.claude/skills/ccswitchmulti-reasoning-tier-repair/

mkdir -p ~/.claude/skills/chatgpt-codex-history-repair
cp -R chatgpt-codex-history-repair/. ~/.claude/skills/chatgpt-codex-history-repair/

mkdir -p ~/.claude/skills/custom-image-gen
cp -R openai/custom-image-gen/. ~/.claude/skills/custom-image-gen/
```

`openwolf-codegraph` 无构建步骤：

```bash
cd openai/openwolf-codegraph
node --check hooks/openwolf.mjs
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

首次本地安装：

```bash
# marketplace 源指向本仓库 openai/ 目录
codex plugin marketplace add /Users/changsailong/BDSYNC/self/AI/tools/my-skills/openai

codex plugin add openwolf-codegraph@my-skills-local
```

安装或更新后：

1. 重新信任 hook
2. 开新 Codex 任务验证（旧任务不热加载）
3. 目标仓库准备 `.codegraph/` 和/或 `.wolf/`

快速验收：

```bash
codex plugin list | rg openwolf-codegraph
codegraph status
```

详细安装、仓库准备、日常使用、卸载与故障排查见 [`openai/openwolf-codegraph/README.md`](./openai/openwolf-codegraph/README.md)。

---

## 目录结构

```
my-skills/
├── codexradar-model-advisor/
│   └── SKILL.md
├── model-delegate/
│   └── SKILL.md
├── ccswitchmulti-reasoning-tier-repair/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/expected-tier-map.json
│   └── scripts/repair.py
├── chatgpt-codex-history-repair/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── openai/
│   ├── .agents/plugins/marketplace.json
│   ├── custom-image-gen/
│   │   ├── SKILL.md
│   │   └── agents/openai.yaml
│   ├── openwolf-codegraph/
│   │   ├── .codex-plugin/plugin.json
│   │   └── hooks/
├── skills.json
├── AGENTS.md
└── README.md
```

---

## License

MIT

---

## 联系

- GitHub: [@steedjson](https://github.com/steedjson)
- Repository: [steedjson/my-skills](https://github.com/steedjson/my-skills)
