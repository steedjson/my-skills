# vlong's Claude Code Skills

个人 Claude Code skills 集合，专注于工作流优化和智能路由。

## 📦 Skills 列表

### [route-effort](./route-effort/)
根据任务复杂度自动路由到合适的 agent `effort` 级别（`low`/`medium`/`high`/`xhigh`/`max`），优化 token 使用和响应速度。

**版本**: 2.4.0  
**特性**:
- 🎯 自动复杂度分析（15+ 维度决策树）
- ✅ **SkillOpt 训练验证**（测试集准确率 80%，Soft 评分 0.950）
- ⚡ SkillOpt 自适应学习（可选）
- 🔧 Workflow 集成
- 🛡️ 13 个安全修复（路径穿越、SQL 注入、secrets 泄露）
- 🪨 **caveman 集成**：支持压缩输出模式（省 65% tokens）

> 📊 **v2.4.0 更新**：通过 50 个真实任务样本的 SkillOpt 训练验证，规则准确率达 80%。详见 [训练报告](./docs/skillopt/training-summary.md) 和 [集成指南](./docs/skillopt/integration-guide.md)。

---

## 🚀 快速开始

**一键安装所有 skills**：

```bash
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash
```

**安装单个 skill**：

```bash
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash -s -- route-effort
```

**完整安装（含 Workflow + SkillOpt）**：

```bash
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash -s -- route-effort --with-workflow --with-skill-opt
```

---

## 📖 安装原理

**v2.4.0 改进**（消除 GitHub API 限流）：
- ✅ **一次网络请求**：clone 整个仓库到临时目录（或 tarball 下载），替代逐文件 curl（20+ 请求）
- ✅ **自动环境检测**：有 `git` → `git clone --depth 1`，无 `git` → `curl tarball`
- ✅ **失败回退**：git clone 失败（限流/离线）自动回退到 tarball
- ✅ **临时清理**：`trap` 确保安装完成后删除临时目录
- ✅ **无限流风险**：告别 429 错误（60 req/hour → 几乎不限）

**开发者模式**（仓库内直接运行）：
```bash
git clone https://github.com/steedjson/my-skills.git
cd my-skills
./install.sh route-effort --with-workflow --with-skill-opt
```
零网络请求，本地文件直接复制。

---

## 🗂️ 目录结构

```
my-skills/
├── install.sh                  # 统一安装入口
├── shared/
│   └── install_skill.sh        # 共享安装函数
├── route-effort/               # route-effort skill
│   ├── SKILL.md                # skill 定义
│   ├── README.md               # 使用文档
│   ├── CHANGELOG.md            # 版本记录
│   ├── effort-routed-task.js   # Workflow 脚本
│   └── scripts/                # SkillOpt 训练脚本
│       ├── log_usage.py
│       ├── train_route_effort.py
│       └── prepare_skillopt_env.py
├── docs/                       # 文档归档
│   ├── setup/                  # Claude Code 设置指南
│   ├── skillopt/               # SkillOpt 训练文档
│   └── automation-recommendations.md
├── skills.json                 # skills 注册表
└── AGENTS.md                   # caveman 规则（通用）
```

---

## 🔧 升级

重新运行安装命令即可覆盖升级：

```bash
curl -fsSL https://raw.githubusercontent.com/steedjson/my-skills/main/install.sh | bash
```

---

## 🪨 caveman 集成

本项目集成了 [caveman](https://github.com/JuliusBrussee/caveman) 压缩输出规则，支持：
- **Cursor**: `.cursor/rules/caveman.mdc`
- **Windsurf**: `.windsurf/rules/caveman.md`
- **Cline**: `.clinerules/caveman.md`
- **GitHub Copilot**: `.github/copilot-instructions.md`
- **OpenCode**: `.opencode/AGENTS.md`
- **通用**: `AGENTS.md`

这些规则会让 AI 助手用压缩风格输出，节省约 65% tokens。Claude Code 通过插件自动启用。

---

## 📜 License

MIT

---

## 🤝 贡献

欢迎提交 Issue 和 PR。如发现安全问题，请私信告知。

---

## 📮 联系

- GitHub: [@steedjson](https://github.com/steedjson)
- Repository: [steedjson/my-skills](https://github.com/steedjson/my-skills)
