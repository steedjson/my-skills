# OpenWolf + CodeGraph

Codex 生命周期插件。桥接仓库本地 OpenWolf hooks，并在存在 CodeGraph 索引时注入优先导航提示。

它不是手动调用的命令面板工具。装好后，在任务开始 / 写文件 / 结束时自动运行。

## 它做什么

| 仓库标记 | 行为 |
|---|---|
| `.codegraph/` | SessionStart 注入：代码探索优先用 `codegraph_explore`，不要先 broad grep/read |
| `.wolf/` | 转发 SessionStart / PreToolUse / PostToolUse / Stop 到仓库 `.wolf/hooks/*` |
| 两者都无 | 安静退出，无输出，不改项目 |

项目特有 OpenWolf 逻辑仍放在各仓库 `.wolf/` 内。插件只做：

1. 适配 Codex 事件 payload
2. 在有 `.codegraph/` 时注入导航提示
3. 删除文件时维护 `.wolf/anatomy.md` / `.wolf/memory.md` 等本地记录

不要和下面两项混淆：

- `codegraph` MCP/CLI：真正查符号、读源码、看调用链
- 仓库 `.wolf/`：项目自己的 OpenWolf 规则 / 记忆 / hook 脚本

## 安装

### 1. 确认 marketplace

本仓库 marketplace 源：

```text
/Users/changsailong/BDSYNC/self/AI/tools/my-skills/openai
```

若 `~/.codex/config.toml` 还没有 `my-skills-local`，先加：

```bash
codex plugin marketplace add /Users/changsailong/BDSYNC/self/AI/tools/my-skills/openai
```

也可用 personal 源：

```text
/Users/changsailong/plugins/openwolf-codegraph
```

### 2. 安装插件

推荐本仓库源：

```bash
codex plugin add openwolf-codegraph@my-skills-local
```

或 personal 源：

```bash
codex plugin add openwolf-codegraph@personal
```

### 3. 信任 hooks

安装 / 更新后必须重新信任 hook。旧任务不会热加载生命周期 hook。

### 4. 开新 Codex 任务

只有新任务才会加载插件 hook。安装后不要继续旧会话验收。

### 5. 确认安装状态

```bash
codex plugin list | rg openwolf-codegraph
```

期望：`installed, enabled`

## 仓库侧准备

### 只要 CodeGraph 导航

```bash
cd /path/to/project
codegraph init
codegraph status
```

仓库根目录出现 `.codegraph/` 后，新开 Codex 任务。SessionStart 应注入类似：

```text
CodeGraph is active. For code discovery and impact analysis, use codegraph_explore with projectPath "..." before grep/find or broad file reads.
```

### 还要 OpenWolf 本地自动化

仓库需有：

```text
.wolf/
  hooks/
    session-start.js
    pre-write.js
    post-write.js
    stop.js
  anatomy.md
  cerebrum.md
  memory.md
```

插件会在：

- 任务开始 → 调 `session-start.js`，并注入 OpenWolf/CodeGraph 上下文
- 写文件前（`apply_patch` / `Edit` / `Write`）→ 调 `pre-write.js`
- 写文件后 → 调 `post-write.js`
- 删除文件后 → 维护 `.wolf/anatomy.md` 与 session 记录
- 任务结束 → 调 `stop.js`

缺少某个 hook 文件时跳过该事件，不阻塞主流程。

## 日常使用

正确用法不是“调用 openwolf-codegraph”，而是：

1. 插件 installed + enabled，hooks 已信任
2. 目标仓库有 `.codegraph/` 和/或 `.wolf/`
3. 新开 Codex 任务
4. 正常问代码 / 改代码

### 代码探索

有 `.codegraph/` 时，agent 应优先：

```text
codegraph_explore(query="登录流程怎么走", projectPath="/path/to/project")
```

或 shell：

```bash
codegraph explore "登录流程怎么走"
codegraph status
codegraph impact SomeSymbol
```

无 `.codegraph/` 时不要强行用 CodeGraph；回退到 `rg` / 直接读文件。

### 写代码时

有 `.wolf/` 时，pre/post-write 自动跑。你不需要额外命令。

## 验证清单

| 检查 | 期望 |
|---|---|
| `codex plugin list` 且过滤 `openwolf-codegraph` | installed, enabled |
| 仓库有 `.codegraph/` | 新任务 SessionStart 出现 CodeGraph 提示 |
| 仓库有 `.wolf/hooks/*` | 写文件时触发 pre/post-write |
| 普通仓库无标记 | 无输出、无副作用 |
| `codegraph status` | 索引存在且 up to date |

源码校验：

```bash
cd openai/openwolf-codegraph
node --check hooks/openwolf.mjs
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

## 更新

改完源码后：

1. 重新安装或刷新插件缓存
2. 重新信任 hooks
3. 开新任务验证

```bash
codex plugin add openwolf-codegraph@my-skills-local
# 或按你当前 marketplace 名称重装
```

## 卸载

```bash
codex plugin remove openwolf-codegraph@my-skills-local
# 或
codex plugin remove openwolf-codegraph@personal
```

卸载后检查：

```bash
codex plugin list | rg openwolf-codegraph
rg -n "openwolf-codegraph" ~/.codex/config.toml
```

注意：

- 卸载插件不会删除仓库 `.wolf/` 或 `.codegraph/`
- 不会卸载 `codegraph` MCP / CLI
- 若 `config.toml` 仍有相关 `hooks.state` / plugin 段，需人工确认清理

## 故障排查

| 现象 | 处理 |
|---|---|
| 装了但无提示 | 确认新任务；确认仓库真有 `.codegraph/` 或 `.wolf/` |
| plugin list 仍 not installed | 检查 marketplace 源路径与插件名 |
| CodeGraph 工具报 not indexed | 在目标仓库跑 `codegraph init` / `codegraph status` |
| OpenWolf 不触发 | 检查 `.wolf/hooks/*.js` 是否存在且可执行于 Node |
| 旧任务行为不变 | 生命周期 hook 不热加载，开新任务 |

## 目录

```text
openwolf-codegraph/
├── .codex-plugin/plugin.json
├── hooks/
│   ├── hooks.json
│   └── openwolf.mjs
└── README.md
```
