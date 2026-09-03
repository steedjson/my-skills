# Gemini Banana Image 配置指南

本文档提供各种常用部署与中转环境下的配置参考。

---

## 1. 自动读取的常用配置位置

脚本会在无需任何入参时自动按以下顺序查找配置（全平台兼容）：

1. **Windows 专有路径**：`%APPDATA%\gemini-banana\config.json`（仅 Windows 存在该环境变量时优先检测）
2. **用户目录跨平台路径**：`~/.config/gemini-banana/config.json`（Windows 上映射至 `C:\Users\<用户名>\.config\gemini-banana\config.json`）
3. **Gemini 客户端通用环境文件**：`~/.gemini/.env`（自动识别 `GOOGLE_GEMINI_BASE_URL` 与 `GEMINI_API_KEY`）
4. **备用配置**：`~/.gemini-banana.json`
5. **系统环境变量**：`GEMINI_BASE_URL` 与 `GEMINI_API_KEY`

---

## 2. 常见场景配置范例

### 场景 A：使用 OneAPI / NewAPI 等聚合渠道

OneAPI / NewAPI 通常将 Google GenAI 代理为 OpenAI 兼容路径或原生 Gemini 路径。

**方式 1：创建 `~/.config/gemini-banana/config.json`**

```bash
mkdir -p ~/.config/gemini-banana
cat > ~/.config/gemini-banana/config.json << 'EOF'
{
  "base_url": "https://api.your-oneapi.com",
  "api_key": "sk-your-oneapi-token",
  "model": "gemini-3.1-flash-image",
  "resolution": "2K"
}
EOF
```

**方式 2：使用环境变量**

```bash
export GEMINI_BASE_URL="https://api.your-oneapi.com"
export GEMINI_API_KEY="sk-your-oneapi-token"
```

---

### 场景 B：使用 Cloudflare Worker / Nginx 自建反代

若在境外服务器自建反向代理：

```json
{
  "base_url": "https://gemini-proxy.your-domain.workers.dev",
  "api_key": "AIzaSyYourOfficialOrProxyKey"
}
```

---

### 场景 C：直接走 Google AI Studio 官方端点

直接在终端或 `~/.zshrc` / `~/.bashrc` 中配置官方 Key 即可，无需设置 `base_url`：

```bash
export GEMINI_API_KEY="AIzaSy..."
```

或者当本地已存在 `~/.gemini/.env` 时，只要执行时带上 `--official` 参数，脚本即会强制忽略本地 proxy base_url：

```bash
uv run scripts/generate_image.py --official --prompt "..."
```

---

## 3. 验证配置状态

任何时候均可通过 `--show-config` 查看生效的配置项（敏感 Key 已打码）：

```bash
uv run scripts/generate_image.py --show-config
```
