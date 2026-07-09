# Claude Code Setup 插件使用指南

## 一、安装

插件已经安装在：`~/.claude/plugins/claude-code-setup`

### 验证安装

```bash
ls -la ~/.claude/plugins/claude-code-setup/
```

应该看到：
```
.claude-plugin/
skills/
README.md
LICENSE
automation-recommender-example.png
```

---

## 二、使用方法

### 方法 1: 直接对话（推荐）

在 Claude Code 中直接问：

```
帮我分析这个项目需要什么 Claude Code 自动化？
```

或者更具体的问题：

```
这个项目应该配置哪些 MCP servers？
推荐一些适合的 hooks 配置
我需要什么 skills？
应该创建哪些 subagents？
```

### 方法 2: 使用 Slash Command

```
/claude-automation-recommender
```

**注意**: 如果命令不可用，说明插件的 skill 还没有被 Claude Code 识别。使用方法 1 代替。

---

## 三、分析输出示例

### 典型输出格式

```markdown
### Codebase Profile
- **Type**: JavaScript/Node.js
- **Framework**: React
- **Key Libraries**: axios, react-router, redux

---

### 🔌 MCP Servers

#### context7
**Why**: React project detected - instant access to React documentation
**Install**: `claude mcp add context7`

#### playwright
**Why**: E2E tests detected - browser automation for testing
**Install**: `claude mcp add playwright`

---

### 🎯 Skills

#### frontend-design
**Why**: React components detected - polish UI consistency
**Create**: `.claude/skills/frontend-design/SKILL.md`
**Invocation**: Both (user and Claude can invoke)
**Also available in**: frontend-design plugin

---

### ⚡ Hooks

#### Auto-format on Write
**Why**: Prettier config detected in package.json
**Where**: `.claude/settings.json`

```json
{
  "hooks": {
    "postToolUse": {
      "Write": "npx prettier --write {file_path}"
    }
  }
}
```

---

### 🤖 Subagents

#### accessibility-checker
**Why**: React UI components need a11y validation
**Where**: `.claude/agents/accessibility-checker.md`

---

**Want more?** Ask for additional recommendations for any category.
**Want help implementing?** Just ask and I can help you set up any of these.
```

---

## 四、针对 my-skills 项目的使用

### 4.1 运行分析

在 my-skills 项目根目录，对 Claude 说：

```
请使用 Claude Code Setup 插件分析 my-skills 项目，
推荐合适的自动化配置。
```

### 4.2 预期推荐

基于 my-skills 项目特征，可能得到以下推荐：

#### MCP Servers
- **filesystem**: 管理多个 skill 文件和目录
- **github**: 自动化 PR、issue 管理

#### Skills
- **skill-development** (from plugin-dev)
  - 用途: 开发新的 skills
  - 原因: my-skills 就是 skills 的集合
  
- **commit** (from commit-commands)
  - 用途: 自动生成 git commit 消息
  - 原因: 频繁的 git 提交操作

#### Hooks
- **Markdown 自动格式化**:
  ```json
  {
    "hooks": {
      "postToolUse": {
        "Write": "npx prettier --write {file_path} --parser markdown",
        "Edit": "npx prettier --write {file_path} --parser markdown"
      }
    }
  }
  ```

- **Skill 验证**:
  ```json
  {
    "hooks": {
      "preToolUse": {
        "Bash(git commit)": "npm run validate-skills"
      }
    }
  }
  ```

#### Subagents
- **documentation-reviewer**: 审查 SKILL.md 的文档质量
- **skill-tester**: 测试 skill 的可用性和完整性

---

## 五、实施推荐

### 5.1 实施 MCP Servers

#### 安装 filesystem MCP
```bash
claude mcp add filesystem
```

配置访问路径（在 `.claude/settings.json` 或 `.mcp.json`）：
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
      "env": {}
    }
  }
}
```

#### 安装 github MCP
```bash
claude mcp add github
```

需要先配置 GitHub token：
```bash
gh auth login
```

### 5.2 实施 Skills

#### 方法 1: 从插件安装（推荐）

```bash
# 安装 plugin-dev 插件
claude plugin install plugin-dev

# 使用 skill-development skill
/skill-development
```

#### 方法 2: 手动创建

创建 `.claude/skills/commit/SKILL.md`：
```markdown
---
name: commit
description: Generate git commit messages
---

# Git Commit Message Generator

Analyze staged changes and generate a conventional commit message.

## Usage

User: `/commit`
```

### 5.3 实施 Hooks

编辑 `.claude/settings.json`：

```json
{
  "hooks": {
    "postToolUse": {
      "Write": "npx prettier --write {file_path}",
      "Edit": "npx prettier --write {file_path}"
    },
    "preToolUse": {
      "Bash(git commit)": "echo 'Running pre-commit checks...' && npm run lint"
    }
  },
  "permissions": {
    "allow": [
      "Read",
      "Write",
      "Edit",
      "Bash(npm *)",
      "Bash(git *)"
    ]
  }
}
```

**注意**: 如果 `.claude/settings.json` 不存在，创建它。

### 5.4 实施 Subagents

创建 `.claude/agents/documentation-reviewer.md`：

```markdown
---
name: documentation-reviewer
description: Review SKILL.md documentation quality
model: claude-sonnet-4
---

# Documentation Reviewer

Review SKILL.md files for:
- Clarity and completeness
- Code examples
- Usage instructions
- Error handling documentation

## Focus Areas

1. **Frontmatter**: name, description, tools
2. **Usage Section**: Clear examples
3. **Edge Cases**: Error handling
4. **Code Quality**: Best practices
```

---

## 六、验证配置

### 6.1 测试 MCP Servers

```
# 在 Claude Code 中
请使用 filesystem MCP 列出 my-skills 目录下的所有 SKILL.md 文件
```

### 6.2 测试 Skills

```
# 如果安装了 commit skill
/commit
```

### 6.3 测试 Hooks

```
# 创建或编辑一个文件，检查是否自动格式化
# 或者尝试提交，检查 pre-commit hook 是否运行
```

### 6.4 测试 Subagents

```
# 使用 Agent tool
请使用 documentation-reviewer 代理审查 route-effort/SKILL.md
```

---

## 七、高级用法

### 7.1 请求特定类型的推荐

```
只推荐 MCP servers 给我
只推荐 hooks 配置
只推荐 skills
```

### 7.2 请求更多选项

在收到初始推荐后：

```
给我更多 MCP server 选项
还有哪些 hooks 可以配置？
推荐更多 skills
```

### 7.3 请求实施帮助

```
帮我实施 context7 MCP server
帮我配置 auto-format hook
帮我创建 skill-development skill
```

---

## 八、常见问题

### Q1: 为什么 /claude-automation-recommender 命令不可用？

**原因**: 插件的 skill 还没有被 Claude Code 识别。

**解决方案**: 使用直接对话方式（方法 1），例如：
```
帮我分析这个项目需要什么 Claude Code 自动化？
```

### Q2: 推荐的配置在哪里？

**MCP Servers**: 
- 全局: `~/.claude/settings.json` 的 `mcpServers` 部分
- 项目: `.mcp.json`

**Skills**:
- 全局: `~/.claude/skills/`
- 项目: `.claude/skills/`
- 插件: `~/.claude/plugins/<plugin-name>/skills/`

**Hooks**:
- 全局: `~/.claude/settings.json` 的 `hooks` 部分
- 项目: `.claude/settings.json`

**Subagents**:
- 项目: `.claude/agents/`

### Q3: 如何选择全局配置还是项目配置？

**全局配置** (适用于所有项目):
- 通用 MCP servers (filesystem, github)
- 通用 hooks (auto-format)
- 个人偏好的 skills

**项目配置** (只适用于当前项目):
- 项目特定的 MCP servers (项目数据库)
- 项目特定的 hooks (特殊构建步骤)
- 项目特定的 skills
- 项目特定的 subagents

**建议**: 
- 先尝试项目配置
- 发现通用价值后提升到全局

### Q4: 配置会自动生效吗？

**MCP Servers**: 需要重启 Claude Code

**Skills**: 立即生效（可能需要刷新）

**Hooks**: 立即生效

**Subagents**: 立即生效

### Q5: 如何共享团队配置？

将项目配置文件提交到 git：

```bash
git add .claude/ .mcp.json
git commit -m "chore: add Claude Code configuration"
git push
```

团队成员 clone 后自动获得相同配置。

### Q6: 推荐不准确怎么办？

插件基于静态分析，可能不完全准确。你可以：

1. **忽略不相关的推荐**
2. **请求更多选项**: "给我更多 XXX 选项"
3. **自定义配置**: 手动添加你需要的自动化
4. **反馈改进**: 记录不准确的案例

---

## 九、实战演练

### 场景 1: 首次设置 my-skills 项目

**步骤 1**: 运行分析
```
帮我分析 my-skills 项目，推荐 Claude Code 自动化配置
```

**步骤 2**: 查看推荐
- 记下推荐的 MCP servers
- 记下推荐的 skills
- 记下推荐的 hooks

**步骤 3**: 实施 MCP（最高优先级）
```bash
claude mcp add filesystem
claude mcp add github
```

**步骤 4**: 实施 Hooks（次优先级）
编辑 `.claude/settings.json`，添加 auto-format hook

**步骤 5**: 测试配置
```
请列出所有 SKILL.md 文件
创建一个测试文件，看是否自动格式化
```

**步骤 6**: 提交配置
```bash
git add .claude/ .mcp.json
git commit -m "chore: add Claude Code automation config"
```

### 场景 2: 优化现有配置

**步骤 1**: 请求优化建议
```
我已经配置了 filesystem MCP，还能加什么？
```

**步骤 2**: 查看新推荐
- 对比已有配置
- 识别缺失的高价值自动化

**步骤 3**: 逐个实施
- 先实施最有价值的 1-2 个
- 测试效果
- 再继续添加

---

## 十、总结

### 使用流程

```
1. 运行分析
   ↓
2. 查看推荐（5 个维度）
   ↓
3. 选择实施（优先级排序）
   ↓
4. 测试验证
   ↓
5. 提交配置（团队共享）
   ↓
6. 定期重新分析（季度或技术栈变化时）
```

### 实施优先级

1. **MCP Servers** - 立即见效，配置简单
2. **Hooks** - 长期受益，一次配置
3. **Skills** - 高度定制，学习成本
4. **Subagents** - 专业场景，复杂配置

### 最佳实践

- ✅ 先实施 1-2 个高价值推荐
- ✅ 测试验证后再扩展
- ✅ 将配置提交到 repo（团队共享）
- ✅ 定期重新运行分析
- ✅ 记录配置效果和改进

---

**文档版本**: 1.0  
**最后更新**: 2024-07-09  
**适用于**: Claude Code Setup Plugin v1.0.0
