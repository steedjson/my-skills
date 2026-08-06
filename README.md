# vlong's Claude Code Skills

个人 Agent Skills 与 Codex 插件源码集合。

## Skills 列表

### [codexradar-model-advisor](./codexradar-model-advisor/)

读取 CodexRadar 当前实测数据与 15 天社区评分历史，为 OpenAI Codex 模型和 reasoning effort 提供质量、速度、成本建议。仅推荐当前有实测数据的组合，支持 Codex、Claude Code 和其他 Agent Skills 兼容宿主。

### [delegate-execution-agent](./delegate-execution-agent/)

建立轻量主 Agent 与执行 Agent 分工。保持主模型不变，优先选择当前可用的 GPT-5.6 Luna Max，其次选择 DeepSeek Flash 的最高实际可用 effort；首选均不可用时，从实时 Agent 列表提供候选。

### [ccswitchmulti-reasoning-tier-repair](./ccswitchmulti-reasoning-tier-repair/)

读取实时 CCSwitchMulti 与 Codex 配置，检查并修复已核实模型的 `low`、`medium`、`high`、`xhigh`、`max`、`ultra` reasoning 档位，并检测已安装 CCSwitchMulti 运行时是否真的支持目标档位。支持检查、预览、备份和写入后 TOML/JSON/数据库验证；未知模型保留原值并报告。

### [django-api-change](./django-api-change/) *(project: wework)*

在 wework 项目中实现、调试或审查 Django API 与 Service 变更。涵盖路由、视图、参数 Schema、Service、模型、迁移、权限、租户隔离、事务、软删除、导出和 API 测试场景。遵循 View → Form/Schema → Service → Model 分层约定。

## Codex 插件

`openai/` 可包含需要构建、测试、安装和显式信任 hook 的 Codex 插件运行时。插件不是独立 Agent Skill，不登记到 `skills.json`。

### [semantic-model-router](./openai/semantic-model-router/)

按任务语义协调 Codex 模型角色。当前只实现安全控制面，不调用模型。

### [openwolf-codegraph](./openai/openwolf-codegraph/)

在用户级统一接入 Codex 生命周期事件。仅当仓库存在 `.wolf/` 或 `.codegraph/` 时启用：转发 OpenWolf 本地 hook，并注入 CodeGraph 优先导航规则。

完整安装 / 使用 / 验证 / 卸载说明见 [`openai/openwolf-codegraph/README.md`](./openai/openwolf-codegraph/README.md)。

---

## 安装

复制 skill 目录下的 `SKILL.md` 到 Claude Code skills 路径：

```bash
mkdir -p ~/.claude/skills/codexradar-model-advisor
cp codexradar-model-advisor/SKILL.md ~/.claude/skills/codexradar-model-advisor/SKILL.md

mkdir -p ~/.claude/skills/delegate-execution-agent
cp delegate-execution-agent/SKILL.md ~/.claude/skills/delegate-execution-agent/SKILL.md

mkdir -p ~/.claude/skills/ccswitchmulti-reasoning-tier-repair
cp -R ccswitchmulti-reasoning-tier-repair/. ~/.claude/skills/ccswitchmulti-reasoning-tier-repair/
```

Codex 插件从各插件目录构建与验证。`semantic-model-router` 当前验证命令：

```bash
cd openai/semantic-model-router
npm test
npm run lint
npm run verify:runtime
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
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

codex plugin add semantic-model-router@my-skills-local
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
├── delegate-execution-agent/
│   └── SKILL.md
├── ccswitchmulti-reasoning-tier-repair/
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/expected-tier-map.json
│   └── scripts/repair.py
├── openai/
│   ├── .agents/plugins/marketplace.json
│   ├── openwolf-codegraph/
│   │   ├── .codex-plugin/plugin.json
│   │   └── hooks/
│   └── semantic-model-router/
│       ├── .codex-plugin/plugin.json
│       ├── hooks/
│       └── src/
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
