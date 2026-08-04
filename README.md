# vlong's Claude Code Skills

个人 Agent Skills 与 Codex 插件源码集合。

## Skills 列表

### [codexradar-model-advisor](./codexradar-model-advisor/)

读取 CodexRadar 当前实测数据与 15 天社区评分历史，为 OpenAI Codex 模型和 reasoning effort 提供质量、速度、成本建议。仅推荐当前有实测数据的组合，支持 Codex、Claude Code 和其他 Agent Skills 兼容宿主。

### [django-api-change](./django-api-change/) *(project: wework)*

在 wework 项目中实现、调试或审查 Django API 与 Service 变更。涵盖路由、视图、参数 Schema、Service、模型、迁移、权限、租户隔离、事务、软删除、导出和 API 测试场景。遵循 View → Form/Schema → Service → Model 分层约定。

## Codex 插件

`openai/` 可包含需要构建、测试、安装和显式信任 hook 的 Codex 插件运行时。插件不是独立 Agent Skill，不登记到 `skills.json`。

### [semantic-model-router](./openai/semantic-model-router/)

按任务语义协调 Codex 模型角色。当前只实现安全控制面，不调用模型。

---

## 安装

复制 skill 目录下的 `SKILL.md` 到 Claude Code skills 路径：

```bash
mkdir -p ~/.claude/skills/codexradar-model-advisor
cp codexradar-model-advisor/SKILL.md ~/.claude/skills/codexradar-model-advisor/SKILL.md
```

Codex 插件从各插件目录构建与验证。`semantic-model-router` 当前验证命令：

```bash
cd openai/semantic-model-router
npm test
npm run lint
npm run verify:runtime
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

首次本地安装：

```bash
codex plugin marketplace add openai
codex plugin add semantic-model-router@my-skills-local
```

安装或更新后，重新信任 hook，并在新 Codex 任务中测试。

---

## 目录结构

```
my-skills/
├── codexradar-model-advisor/
│   └── SKILL.md
├── openai/
│   ├── .agents/plugins/marketplace.json
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
