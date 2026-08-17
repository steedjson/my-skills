# vlong's Agent Skills & Codex Plugins

个人 Agent Skills 与 Codex 插件源码集合。

仓库布局：

- `skills.json`：Skill 注册表，`category` 仅用于分类展示，不决定路径。
- `<skill-name>/`：根目录下每个含 `SKILL.md` 的目录是一个独立可分发 Skill。
- `plugins/<plugin-name>/`：可安装的 Codex 插件包。
- `.agents/plugins/marketplace.json`：仓库插件 marketplace 目录。

## Skills 列表

### 模型与路由（models-and-routing）

#### [codexradar-model-advisor](./codexradar-model-advisor/)

读取 CodexRadar 当前实测数据与 15 天社区评分历史，为 OpenAI Codex 模型和 reasoning effort 提供质量、速度、成本建议。仅推荐当前有实测数据的组合，支持 Codex、Claude Code 和其他 Agent Skills 兼容宿主。

#### [model-delegate](./model-delegate/)

使用 Codex App 原生顶层任务建立低上下文成本分工。默认 `HANDOFF` 单向交接：新任务直接完成工作，旧主任务不等待、不轮询、不验收；任务包强制区分 `READ_ONLY` 与 `WRITE`。委派前必须明确确认模型、effort；运行面没有硬费用熔断时，还必须确认接受软预算风险。

#### [ccs-restore-efforts](./ccs-restore-efforts/)

当 CC Switch 同步模型目录或重写 `config.toml` 后，模型依赖的 `Effort` 和 `Speed` 元数据可能回归。运行 `scripts/restore_efforts.py restore-ui` 会按 Codex Auto Review、DeepSeek V4、Grok 4.5/4.6 与 GPT-5.6/5.5/5.4/5.4-mini/5.2 官方档位、上下文和输出上限收敛，并给其他模型补回通用推理档位、`Fast / priority` 速度档位及丢失的 `model` 行。

### 媒体生成（media-generation）

#### [custom-image-gen](./custom-image-gen/)

通过 `image_auth.json` 和当前 Codex provider 配置解析自定义图片生成端点与凭据（Key 缺失时回退 `auth.json` 的 `OPENAI_API_KEY`），再复用系统 `imagegen` Skill 和 CLI。仅负责 provider 适配，不复制系统图片生成工作流。

### 框架工作流（framework-workflows）

#### [django-development](./django-development/)

在任意 Django 后端项目中发现并遵循现有约定，完成实现、调试、审查或审计。覆盖原生 Django、Django REST Framework、Django Ninja，以及 API、Service/用例、模型、迁移、Admin、Form、后台任务、信号、管理命令、设置和测试。

## Codex 插件

`plugins/` 存放需要构建、测试、安装和显式信任 hook 的 Codex 插件运行时。插件不是独立 Agent Skill，不登记到 `skills.json`。仓库插件目录为 `.agents/plugins/marketplace.json`。

### [openwolf-codegraph-bridge](./plugins/openwolf-codegraph-bridge/)

在用户级统一接入 Codex 生命周期事件。仅当仓库存在 `.wolf/` 或 `.codegraph/` 时启用：转发 OpenWolf 本地 hook，并注入 CodeGraph 优先导航规则。

完整安装 / 使用 / 验证 / 卸载说明见 [`plugins/openwolf-codegraph-bridge/README.md`](./plugins/openwolf-codegraph-bridge/README.md)。

---

## 安装

### 名称迁移

- `openwolf-codegraph@my-skills-local` 已更名为 `openwolf-codegraph-bridge@vlong-skills-local`。
- 仓库改名不会自动删除已安装的旧 Skill、旧插件或旧 marketplace 注册。先安装并验证新名称，再按实际安装状态清理旧条目。

复制 skill 目录下的 `SKILL.md` 到 Claude Code skills 路径：

```bash
mkdir -p ~/.claude/skills/codexradar-model-advisor
cp codexradar-model-advisor/SKILL.md ~/.claude/skills/codexradar-model-advisor/SKILL.md

mkdir -p ~/.claude/skills/model-delegate
cp -R model-delegate/. ~/.claude/skills/model-delegate/

mkdir -p ~/.claude/skills/custom-image-gen
cp -R custom-image-gen/. ~/.claude/skills/custom-image-gen/
```

`openwolf-codegraph-bridge` 无构建步骤：

```bash
cd plugins/openwolf-codegraph-bridge
node --check hooks/openwolf.mjs
python3 <plugin-creator-root>/scripts/validate_plugin.py .
```

首次本地安装：

```bash
# marketplace 源指向本仓库根目录（.agents/plugins/marketplace.json）
codex plugin marketplace add <repo-root>

codex plugin add openwolf-codegraph-bridge@vlong-skills-local
```

安装或更新后：

1. 重新信任 hook
2. 开新 Codex 任务验证（旧任务不热加载）
3. 目标仓库准备 `.codegraph/` 和/或 `.wolf/`

快速验收：

```bash
codex plugin list | rg openwolf-codegraph-bridge
codegraph status
```

详细安装、仓库准备、日常使用、卸载与故障排查见 [`plugins/openwolf-codegraph-bridge/README.md`](./plugins/openwolf-codegraph-bridge/README.md)。

---

## 目录结构

```
my-skills/
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── codexradar-model-advisor/
│   └── SKILL.md
├── model-delegate/
│   ├── SKILL.md
│   └── references/compact-coordinator.md
├── custom-image-gen/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── django-development/
│   ├── SKILL.md
│   └── agents/openai.yaml
├── plugins/
│   └── openwolf-codegraph-bridge/
│       ├── .codex-plugin/plugin.json
│       └── hooks/
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
