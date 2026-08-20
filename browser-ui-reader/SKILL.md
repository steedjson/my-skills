---
name: browser-ui-reader
description: 看浏览器、操作浏览器页面、把 UI 设计图/原型转成结构化需求清单。macOS + Google Chrome。主体用 agent-browser（CDP、可访问性树 @eN refs、零 Playwright 依赖）；AppleScript+JS 注入作为零配置后备（不重启、直接附着已打开的 Chrome，只读为主）。Use when 用户要 看浏览器内容、操作浏览器页面、爬原型/设计稿站点、UI 设计图转需求、提取页面文本或图片、宽表格截图逐列读取。
---

# Browser UI Reader

三层分工：

1. **看 + 操作用户浏览器** → `agent-browser`（首选，Rust CLI + CDP），或 `scripts/chrome_*.sh`（后备，AppleScript 注入，零依赖）。
2. **素材提取** → `screenshot --full` / `read` / JS 提取图片 URL + `scripts/asset_download.sh` + `scripts/wide_crop.py`（宽图分段）。
3. **UI 设计图 → 需求** → 本技能工作流 D + `references/ui-requirements-template.md`。这层是 LLM 工作流，工具只提供素材。

## 前置与自检

```bash
# 首选：agent-browser（本机已装则跳过安装）
which agent-browser || npm i -g agent-browser
agent-browser install            # 首次：下载 Chrome for Testing
agent-browser open https://example.com && agent-browser snapshot -i && agent-browser close

# 官方指令与 CLI 版本锁定同步，命令拿不准时现场取，别凭缓存记忆
agent-browser skills list                    # core / dogfood / derive-client / electron / slack ...
agent-browser skills get core --full         # 完整核心用法
agent-browser upgrade                        # 升级
```

```bash
# 后备：AppleScript 注入自检（要求 Chrome：显示 → 开发者 → 允许 Apple 事件中的 JavaScript）
bash scripts/chrome_tabs.sh
```

## 会话纪律（agent-browser 必做）

默认会话是全机共享的长驻浏览器，可能劫持别人打开的页面。任何任务先命名会话：

```bash
export AGENT_BROWSER_SESSION="$(agent-browser session id --scope worktree --prefix task)"
# 结束：agent-browser close（或 close --all）
# 空闲守护默认 1 小时后保存状态并退出；要自动恢复加 --restore
```

## 工作流

### A. 看页面

**公开/新页面**（agent-browser 自带浏览器）：

```bash
agent-browser open <url>
agent-browser snapshot -i        # 可交互元素 + @eN refs，~200-400 tokens
agent-browser snapshot -i -c -s "#main"   # -c 紧凑 / -s 限定范围 / -d N 限深 / -u 带链接 / --json
agent-browser get text body      # 或 get title / get url
agent-browser read <url>         # 静态内容直取（不启浏览器，llms.txt 感知，--outline/--filter 可用）
```

**用户已打开、已登录的 Chrome**（三选一，按摩擦排序）：

1. `--auto-connect`：自动发现本机的调试端口 Chrome 附着。需先按第 3 步把 Chrome 带调试端口重启一次。
2. `--cdp 9222`：显式连端口。附着后 `tab list` 看用户全部标签，`tab <index>` 切到目标页，`--pin-tab` 把会话钉死在该 tab（防串页、tab 关了报 `tab_gone` 而不是误点别的页）。
3. **零端口零重启（只读）**：`bash scripts/chrome_eval.sh <url片段> '<js>'` 直接注入用户当前 Chrome（见 B 的后备片段）。不能点击导航/等复杂交互时再让用户重启 Chrome 带 `--remote-debugging-port=9222`。

> 安全：调试端口 = 本机任意进程全量控制该浏览器（读 cookie、执行 JS）。仅信任机器用，用完关。

### B. 操作页面

核心回路（**refs 在页面变化后立刻失效，每次交互后必须重新 snapshot**）：

```bash
agent-browser snapshot -i
agent-browser click @e3
agent-browser fill @e5 "text"
agent-browser wait --load networkidle
agent-browser snapshot -i          # 再操作
```

- 语义定位（不依赖 refs）：`find role button click --name "Submit"` / `find text "页面名" click` / `find label "邮箱" fill "a@b.c"`
- 等待：`wait --text "欢迎"` / `wait --fn "window.ready === true"` / `wait "#spinner" --state hidden`
- 批量（多步省启动开销）：`agent-browser batch --bail "open <url>" "snapshot -i" "click @e2"`
- 复杂流程模板（登录、表单、抓数据）：`references/agent-browser-recipes.md`

**后备（AppleScript JS 注入，用户当前 Chrome，无需调试端口）**：

```bash
bash scripts/chrome_eval.sh xiaopiu.com "document.title"
bash scripts/chrome_eval.sh xiaopiu.com "[...document.querySelectorAll('li')].find(e=>e.textContent.trim()==='页面名'&&e.offsetParent)?.click()"
sleep 1.2
bash scripts/chrome_eval.sh xiaopiu.com "JSON.stringify({text: document.body.innerText.slice(0,120000)})"
```

点击类片段（展开折叠、按名点页、取图、填框）：`references/spa-crawl-recipes.md`。

**默认只读。写操作（提交/审批/删除/表单落值）先向用户逐条复述将做什么，确认后再执行。** 禁止：填密码、自动点「提交/删除/审批」、把凭据写进页面。

### C. SPA 原型逐页爬取（xiaopiu 52 页已验证）

0. **交付物给人看（UI/功能清单）→ 截图优先**：逐页 `screenshot --full` + 批量视觉读，直出清单；DOM 文本只作回查（精确星号/隐藏字段/宽表分段）。配方见 recipes「截图优先模式」。

1. 展开全部折叠文件夹 → 枚举页面树 → `pages.txt`（带层级，区分文件夹/页面；全局枚举会混入顶部导航节点，落盘时过滤）。
2. 逐页：`find text "页面名" click`（或 JS 注入）→ `sleep 1.2` / `wait --text` → 提取 innerText → `crawl/NN_页面名.txt`。
3. 收尾核对：爬到的页数 = pages.txt 页数；缺页单独重试。
4. 已验证选择器/JS 片段：`references/spa-crawl-recipes.md`。
5. 需要登录态 → 先走 A「用户已打开 Chrome」附着流程，再爬。

### D. UI 设计图/原型 → 需求清单

1. 素材：`agent-browser screenshot --full page.png`（整页长图）；设计图 URL 用 JS 提取（`[...document.images].map(i=>i.currentSrc||i.src)`）→ `scripts/asset_download.sh <urls文件> <目录>`。
2. 先分型再分析：小图标（<100px）/ UI 组件条 / **数据宽表（宽>2500px）** / **实拍照片（原型常用的场景素材，不是 UI mockup，别当界面解析）**。
3. 宽表：`python3 scripts/wide_crop.py <图> <目录> --seg 1200` 切带重叠分段，逐段读列头+样例行。同 md5 去重。
4. 按 `references/ui-requirements-template.md` 合并输出：导航层 / 模块-页面-字段-操作 / 审批状态机 / 向导步骤 / 模板机制 / 设计系统 / 疑点清单 / **采集盲区**。
5. 落盘 `<项目名>-UI功能清单.md`，附来源地址、采集方式与时间。

## 官方专项 skill（随 CLI 版本）

`core` 已并入本技能。其余按 task 现取，版本锁定、不缓存：

- `agent-browser skills get dogfood --full` — 系统化探索 web 应用找 bug / UX 问题
- `agent-browser skills get derive-client --full` — 录流量反推站点内部 API
- `agent-browser skills get electron --full` — 驱动 Electron 桌面应用
- `agent-browser skills get slack --full` — 浏览器自动化操作 Slack

## 安全

- 只读默认；写操作逐项确认；不动凭据。
- `--remote-debugging-port` 仅限信任机器，用完关闭 Chrome。
- 不受信任站点加护栏：`--allowed-domains`、`--max-output`。
- 认证状态文件（`state save`）含明文 token：加 `.gitignore`、及时删、可设 `AGENT_BROWSER_ENCRYPTION_KEY` 加密。
