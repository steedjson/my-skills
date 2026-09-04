# Grok Image 配置指南

本文档提供各种常用部署与中转环境下的配置参考。

---

## 1. 自动读取的常用配置位置

脚本会在无需任何入参时自动按以下顺序查找配置（全平台兼容）：

1. **Windows 专有路径**：`%APPDATA%\grok-image\config.json`（仅 Windows 存在该环境变量时优先检测）
2. **用户目录跨平台路径**：`~/.config/grok-image/config.json`（Windows 映射至 `C:\Users\<用户名>\.config\grok-image\config.json`）
3. **Grok CLI 本地配置**：`~/.grok/config.toml`（自动提取其中的 `base_url` 与 `api_key`）
4. **备用配置**：`~/.grok-image.json`
5. **系统环境变量**：`XAI_API_KEY` / `GROK_API_KEY` 与 `XAI_BASE_URL` / `GROK_BASE_URL`

---

## 2. 常见场景配置范例

### 场景 A：使用 OneAPI / NewAPI 等第三方中转渠道

**方式 1：创建 `~/.config/grok-image/config.json`**

```bash
mkdir -p ~/.config/grok-image
cat > ~/.config/grok-image/config.json << 'EOF'
{
  "base_url": "https://api.your-oneapi.com/v1",
  "api_key": "sk-your-oneapi-token",
  "model": "grok-imagine-image"
}
EOF
```

**方式 2：使用环境变量**

```bash
export XAI_BASE_URL="https://api.your-oneapi.com/v1"
export XAI_API_KEY="sk-your-oneapi-token"
```

---

### 场景 B：直接走 xAI 官方端点

直接在终端或 `~/.zshrc` / `~/.bashrc` 中配置 xAI 官方 Key 即可：

```bash
export XAI_API_KEY="xai-..."
```

或者当本地已存在 `~/.grok/config.toml` 时，执行时带上 `--official` 参数即可强制直连官方端点：

```bash
uv run scripts/generate_image.py --official --prompt "..."
```

---

## 3. 账号体系说明与常见排查

### 体系区别
- **C 端订阅**：X Premium / SuperGrok 等月费订阅，只能在网页或官方 App 界面对话，**不包含官方 API 额度**。
- **开发者平台**：必须在 [console.x.ai](https://console.x.ai) 绑定信用卡并开通 API Key（格式通常为 `xai-...`）。

### 常见错误：`503 No eligible Grok media accounts`
- **原因**：如果配置了第三方中转网关（如 Sub2API、OneAPI），该网关转发图片使用的是后台维护的 Grok 网页媒体账号池。当网关账号全部失效、过期或被风控时，就会报此错。
- **解决**：换用官方开发者 Key，或者在网关后台重新导入有效的 Grok 媒体会话账号。

---

## 4. 验证配置状态

任何时候均可通过 `--show-config` 查看生效的配置项（敏感 Key 已脱敏）：

```bash
uv run scripts/generate_image.py --show-config
```
