---
name: gemini-banana-image
description: 使用 Google Gemini 图像模型（Gemini 3 Pro Image / Nano Banana Pro / Imagen 3）生成与编辑图片。支持双通道智能路由：有自定义 base_url 与 key 时自动走中转/自建代理，无自定义配置或指定官方时自动回退 Google 官方端点。适用于文生图、图生图编辑、自定义端点生图等场景。
---

# Gemini Banana Image

使用 Google Gemini 图像模型（如 `gemini-3-pro-image-preview` / Nano Banana Pro）进行高质量 AI 图片生成与编辑。具备自定义中转端点（OneAPI / NewAPI / 自建反代）与 Google 官方端点之间的无缝自适应路由。

## 核心特性

- **双通道自适应路由**：优先读取用户自定义的 `base_url` 与 `api_key`；未配置自定义端点时无缝回退官方 Google AI。
- **Thinking 流解析**：支持 Gemini 多模态思考链流式输出，自动捕获过滤过程草图并提取最终高清图像。
- **分辨率与比例**：支持 1K / 2K / 4K 分辨率，以及 1:1、16:9、9:16、4:3、3:4 等构图比例。
- **图生图编辑**：传入 `--input-image` 可基于已有图片按提示词进行局部修改或风格变换。

## 配置优先级

脚本按以下优先级依次解析端点与密钥（高到低）：

1. **CLI 显式参数**：`--base-url`, `--api-key`, `--model`, `--official`
2. **显式指定配置文件**：`--config /path/to/config.json` 或 `.env`
3. **用户常驻配置**（自动检测）：
   - `~/.config/gemini-banana/config.json`
   - `~/.gemini/.env`（自动识别 `GOOGLE_GEMINI_BASE_URL` / `GEMINI_BASE_URL` 与 `GEMINI_API_KEY`）
   - `~/.gemini-banana.json`
4. **环境变量**：`GEMINI_BASE_URL`, `GEMINI_API_KEY`, `GEMINI_IMAGE_MODEL`
5. **官方端点回退**：若未探测到有效 `base_url`，自动走官方 `https://generativelanguage.googleapis.com`。

## 未配置时的处理流程 (Agent 行为约定)

当执行生图因缺少 API Key 报错时：
1. **主动引导**：向用户明确提示当前缺少配置，询问用户希望使用【官方 Google AI Key】还是【第三方中转 Base URL + Key】。
2. **协助落盘**：获得用户提供的配置后，可直接协助写入 `~/.config/gemini-banana/config.json`（或 `~/.gemini/.env`），实现永久免配置。
3. **无缝重试**：写入完成后自动重新执行生图命令，无需用户再次重复输入生图描述。

### 配置文件范例 (`~/.config/gemini-banana/config.json`)

```json
{
  "base_url": "https://api.your-proxy.com",
  "api_key": "sk-your-key",
  "model": "gemini-3-pro-image-preview",
  "resolution": "1K"
}
```

## 使用方法

始终在用户当前工作目录下调用脚本（使用绝对路径或相对仓库路径）：

### 1. 检查当前解析的配置

无需真正发请求，快速校验端点与密钥是否就绪：

```bash
uv run {baseDir}/scripts/generate_image.py --show-config
```

### 2. 生成新图片 (Text-to-Image)

```bash
uv run {baseDir}/scripts/generate_image.py --prompt "赛博朋克风格的雨夜街道，霓虹灯倒影，高清质感" --filename "cyberpunk.png" --aspect-ratio "16:9" --resolution "2K"
```

### 3. 基于已有图片编辑 (Image-to-Image)

```bash
uv run {baseDir}/scripts/generate_image.py --prompt "将背景替换为落日余晖下的雪山" --input-image "input.png" --filename "edited.png"
```

### 4. 强制走官方端点 (绕过本地自定义 base_url)

```bash
uv run {baseDir}/scripts/generate_image.py --official --prompt "极简风格香蕉插画" --filename "banana.png"
```

### 5. 显式临时指定自定义中转

```bash
uv run {baseDir}/scripts/generate_image.py --base-url "https://api.custom-proxy.com" --api-key "sk-xxxx" --prompt "日式水彩浮世绘风格的富士山" --filename "fuji.png"
```

## 参数说明

| 参数 | 缩写 | 默认值 | 说明 |
|---|---|---|---|
| `--prompt` | `-p` | (必填) | 图像描述提示词或编辑指令 |
| `--filename` | `-f` | 自动生成时间戳文件 | 输出 PNG 文件路径 |
| `--input-image` | `-i` | None | 输入图片路径（用于图生图编辑） |
| `--resolution` | `-r` | `1K` | 分辨率：`1K`、`2K`、`4K` |
| `--aspect-ratio`| `-a` | None | 比例：`1:1`、`16:9`、`9:16`、`4:3`、`3:4` |
| `--model` | `-m` | `gemini-3-pro-image-preview` | 模型名称 |
| `--base-url` | | 自动检测 | 自定义 API Base URL |
| `--official` | | False | 强制使用 Google 官方直连端点 |
| `--api-key` | `-k` | 自动检测 | API 密钥 |
| `--config` | `-c` | 自动检测 | 显式指定 JSON 或 .env 配置文件 |
| `--show-config`| | False | 仅打印解析出的当前配置并退出 |

## 产出规范

- 图片直接保存在用户指定的路径或当前目录下。
- 脚本成功执行后输出包含绝对路径的确认信息：`Image successfully generated and saved: <path>`。
- Agent 在生成完成后应直接向用户反馈生成文件的路径和状态，按需使用图片查看工具或展示结果。
