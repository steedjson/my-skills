# agent-browser 配方（本机验证过命令面 v0.17.1）

## 会话

```bash
# 命名会话（每个任务一套，防共享默认会话串页）
export AGENT_BROWSER_SESSION="$(agent-browser session id --scope worktree --prefix 任务名)"
agent-browser session list

# 状态自动持久化（cookies/localStorage，跨重启）
agent-browser --session-name myapp open https://app.example.com/dashboard

# 结束
agent-browser close
```

## 附着用户已打开的 Chrome（登录态）

```bash
# 1) Chrome 带调试端口重启（标签保留；本机全量控制面，仅信任机器）
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222

# 2) 附着 + 看标签 + 切目标页
agent-browser --auto-connect tab list          # 自动发现运行中的 Chrome
agent-browser --cdp 9222 tab 3                 # 切到第 3 个标签
agent-browser --cdp 9222 tab list --json       # 拿 targetId / URL 精确对页

# 3) 钉住该 tab（防串页；tab 被关报 tab_gone 而非误操作别的页）
agent-browser --session 任务名 --cdp 9222 --pin-tab open https://site-a.com
```

从已登录 Chrome 导认证态到自动化 profile（复杂 OAuth/SSO/2FA 都适用）：

```bash
agent-browser --auto-connect state save ./auth.json
agent-browser --state ./auth.json open https://app.example.com/dashboard
# 或登录一次后用持久 profile
agent-browser --profile /path/to/user-data-dir open ...
```

## 交互核心回路

```bash
agent-browser snapshot -i                  # 可交互元素 + @eN refs
agent-browser click @e3
agent-browser fill @e5 "text@example.com"
agent-browser press Enter
agent-browser wait --load networkidle
agent-browser snapshot -i                  # refs 已变化，重新取
```

refs 规则：**每次页面变化后引用即失效**（导航、表单提交、重渲染、弹层）。交互后必 snapshot。点击被遮挡（横幅/弹窗）会提前失败并报告遮挡元素 → 先处理遮挡项再重新 snapshot。

## 语义定位（无需 refs）

```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "a@b.c"
agent-browser find placeholder "Search" type "kw"
agent-browser find first ".item" click
agent-browser find nth 2 "a" text
```

## 等待

```bash
agent-browser wait "#app"                  # 元素可见
agent-browser wait 1200                     # 毫秒
agent-browser wait --text "Welcome"         # 文本出现
agent-browser wait --url "**/dash"          # URL 匹配
agent-browser wait --load networkidle
agent-browser wait --fn "window.ready === true"
agent-browser wait "#spinner" --state hidden
```

## 批量 / 检查 / 读取

```bash
agent-browser batch --bail "open https://x" "snapshot -i" "click @e2" "screenshot step.png"

agent-browser is visible "#form"
agent-browser is enabled "#btn"

agent-browser read                            # 活动 tab 渲染后 DOM 的可读文本
agent-browser read https://docs.example.com --outline
agent-browser read https://docs.example.com --llms index --filter auth
```

## 截图 / 提取

```bash
agent-browser screenshot page.png            # 默认视口
agent-browser screenshot --full page.png     # 整页长图（UI 解析用这个）
agent-browser screenshot --annotate          # 带编号标注（refs 可视化）
agent-browser pdf out.pdf
agent-browser eval "JSON.stringify([...document.images].map(i=>i.currentSrc || i.src))"
agent-browser get box "#table"               # 定位宽表区域
```

## 表单 / 上传 / 键盘

```bash
agent-browser fill "#email" "a@b.c"
agent-browser select "#plan" "pro"
agent-browser check "#agree"
agent-browser upload "#file" ./a.png
agent-browser keyboard type "raw text"       # 当前焦点
agent-browser press Tab
agent-browser drag "#a" "#b"
```

## 护栏

```bash
agent-browser open https://untrusted.example --allowed-domains untrusted.example
# 全局输出上限：--max-output
```
