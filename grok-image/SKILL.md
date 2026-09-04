---
name: grok-image
description: 使用 xAI Grok 图像模型（默认 grok-imagine-image，亦支持 grok-2-image 等）文生图。支持双通道智能路由：有自定义 base_url 与 key 时自动走中转/自建代理（自动兼容 ~/.grok/config.toml 与 ~/.config/grok-image/config.json），无自定义配置或指定 --official 时自动回退 xAI 官方端点。默认保存至系统临时目录，避免污染代码库。
---

# Grok Image

使用 xAI Grok 图像模型（默认 `grok-imagine-image`，亦支持 `grok-2-image`）进行高质量 AI 图片生成。具备自定义中转端点（OneAPI / NewAPI / 自建反代）与 xAI 官方端点之间的无缝自适应路由。

## 核心特性

- **双通道自适应路由**：优先读取用户自定义的 `base_url` 与 `api_key`；未配置自定义端点或显式指定 `--official` 时自动回退 xAI 官方端点 (`https://api.x.ai/v1`)。
- **自动识别本地 Grok 环境**：自动无缝探测读取 `~/.grok/config.toml`，复用本地既有的 Grok CLI 凭据与反代端点。
- **临时目录保护**：默认输出至系统临时目录（macOS/Linux: `<TEMP>/grok-image/`，Windows: `%TEMP%\grok-image\`），绝不污染工作目录。
- **全平台兼容**：完美兼容 Windows (PowerShell / CMD)、macOS 与 Linux。

## 配置优先级

脚本按以下优先级依次解析端点与密钥（高到低）：

1. **CLI 显式参数**：`--base-url`, `--api-key`, `--model`, `--official`
2. **显式指定配置文件**：`--config /path/to/config.json`
3. **用户常驻配置**（自动检测）：
   - `~/.config/grok-image/config.json`（Windows 上支持 `%APPDATA%\grok-image\config.json`）
   - `~/.grok/config.toml`（读取既有模型端点配置）
   - `~/.grok-image.json`
4. **环境变量**：`XAI_BASE_URL` / `GROK_BASE_URL`, `XAI_API_KEY` / `GROK_API_KEY`, `GROK_IMAGE_MODEL`
5. **官方端点回退**：若未配置自定义端点，默认直连官方 `https://api.x.ai/v1`。

## 账号与计费体系说明 (重要必读)

Grok 的 C 端订阅与开发者 API 是**两套完全隔离的独立计费与账户体系**：

| 体系类型 | 包含产品 | 适用范围与说明 | 能否直接用于此 API |
|---|---|---|---|
| **C 端用户订阅** | X Premium / Premium+ / SuperGrok 订阅 | 仅面向网页端/移动端 App 交互界面，按月计费；**不包含**任何开放 API 额度，官方不提供向普通订阅用户开放的图片 API。 | ❌ 不能直接调用（第三方网关如 Sub2API 会尝试模拟网页会话，但若其媒体账号池失效会报错） |
| **B 端开发者平台** | xAI Console ([console.x.ai](https://console.x.ai)) | 面向程序调用的标准开发者 API，绑定信用卡按量计费（Pay-as-you-go，图片约 $0.02/张），提供正规 `xai-...` API Key。 | ✅ 官方标准支持，稳定高可用 |

### 常见报错排查

- **报错：`503 No eligible Grok media accounts` (或 `grok_media_no_eligible_account`)**
  - **根因**：当前配置走的是第三方中转/网关服务（如 Sub2API），该网关后台用于转发 Grok 图片的网页端媒体账号池（Cookie/Session）已全部失效或额度耗尽。
  - **对策**：
    1. 前往 [console.x.ai](https://console.x.ai) 注册开发者账号并获取官方 `xai-...` Key，在配置中切换为官方端点；
    2. 或等待中转网关管理员更新补充可用的 Grok 媒体账号池。

## 未配置时的处理流程 (Agent 行为约定)

当执行生图因缺少 API Key 报错时：
1. **主动引导**：向用户明确提示当前缺少配置，询问用户希望使用【官方 xAI Key】还是【第三方中转 Base URL + Key】。
2. **协助落盘**：获得用户提供的配置后，可直接协助写入 `~/.config/grok-image/config.json`，实现永久免配置。
3. **无缝重试**：写入完成后自动重新执行生图命令，无需用户再次重复输入生图描述。

### 配置文件范例 (`~/.config/grok-image/config.json`)

```json
{
  "base_url": "https://api.your-proxy.com/v1",
  "api_key": "sk-your-key",
  "model": "grok-2-image"
}
```

## 使用方法

始终在用户当前工作目录下调用脚本：

### 1. 检查当前解析的配置

无需真正发请求，快速校验端点与密钥是否就绪：

```bash
uv run {baseDir}/scripts/generate_image.py --show-config
```

### 2. 生成新图片 (Text-to-Image)

```bash
uv run {baseDir}/scripts/generate_image.py --prompt "赛博朋克风黑猫在霓虹雨夜中奔跑，高画质，电影级光影" --filename "grok-cat.png"
```

### 3. 强制走 xAI 官方端点 (绕过本地自定义 base_url)

```bash
uv run {baseDir}/scripts/generate_image.py --official --prompt "未来主义城市天际线，黄昏时刻"
```

### 4. 显式临时指定自定义中转

```bash
uv run {baseDir}/scripts/generate_image.py --base-url "https://api.custom-proxy.com/v1" --api-key "sk-xxxx" --prompt "日式浮世绘海浪"
```

## 参数说明

| 参数 | 缩写 | 默认值 | 说明 |
|---|---|---|---|
| `--prompt` | `-p` | (必填) | 图像描述提示词 |
| `--filename` | `-f` | 时间戳命名的 PNG | 输出文件名（裸文件名自动存入临时目录，也可填绝对路径） |
| `--output-dir`| `-o` | `<TEMP>/grok-image` | 输出目录，默认采用系统临时目录避免污染代码库 |
| `--model` | `-m` | `grok-imagine-image` | 模型名称（亦可指定 `grok-2-image` 等） |
| `--aspect-ratio`| `-a` | None | 比例：`1:1`、`16:9`、`9:16`、`4:3`、`3:4`（若中转端点支持） |
| `--base-url` | | 自动检测 | 自定义 API Base URL |
| `--official` | | False | 强制使用 xAI 官方直连端点 |
| `--api-key` | `-k` | 自动检测 | API 密钥 |
| `--config` | `-c` | 自动检测 | 显式指定 JSON 配置文件 |
| `--show-config`| | False | 仅打印解析出的当前配置并退出 |

## 产出规范

- **临时目录存储**：默认保存至系统临时文件夹（macOS/Linux 为 `<TEMP>/grok-image/`，Windows 为 `%TEMP%\grok-image\`），绝不污染代码库。
- **用户提示与下载**：脚本执行完毕后输出生成的绝对路径，Agent 需向用户提供 Markdown 文件链接（如 `[name.png](/path/to/file.png)`），方便用户直接点击预览或下载另存。
