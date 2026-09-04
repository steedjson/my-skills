#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pillow>=10.0.0",
#     "requests>=2.31.0",
# ]
# ///
"""
Generate images using xAI Grok Image models (e.g. grok-2-image, grok-2-image-1212).

Supports:
- Dual-channel routing: custom base_url + key (e.g. OneAPI / NewAPI / proxy) with automatic fallback to official xAI API.
- Multi-tier config resolution: CLI args > Config file > ~/.config/grok-image/config.json > ~/.grok/config.toml > Environment variables > Official fallback.
- Standard OpenAI-compatible /v1/images/generations endpoint.
- Automatic image decoding (base64 or URL download).
- Platform-safe default output to system temporary directory (<TEMP>/grok-image).
"""

import argparse
import base64
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None

OFFICIAL_BASE_URL = "https://api.x.ai/v1"
DEFAULT_MODEL = "grok-imagine-image"


def get_config_candidates() -> list:
    """Return platform-aware candidate paths for configuration files."""
    candidates = []
    # Windows native AppData
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "grok-image" / "config.json")

    # Cross-platform user config directory
    candidates.extend([
        Path.home() / ".config" / "grok-image" / "config.json",
        Path.home() / ".grok-image.json",
    ])
    return candidates


def load_json_file(filepath: Path) -> dict:
    """Parse a JSON configuration file."""
    if not filepath.exists() or not filepath.is_file():
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed reading {filepath}: {e}", file=sys.stderr)
        return {}


def load_grok_cli_config() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Attempt reading base_url and api_key from ~/.grok/config.toml."""
    grok_toml = Path.home() / ".grok" / "config.toml"
    if not grok_toml.exists() or not grok_toml.is_file() or not tomllib:
        return None, None, None

    try:
        with open(grok_toml, "rb") as f:
            data = tomllib.load(f)
            # Find default model or any model with base_url / api_key
            default_name = data.get("models", {}).get("default")
            models = data.get("model", {})

            # Try default model first
            if default_name and default_name in models:
                m_info = models[default_name]
                b_url = m_info.get("base_url")
                k = m_info.get("api_key")
                if b_url or k:
                    return b_url, k, default_name

            # Scan any configured model
            for m_name, m_info in models.items():
                b_url = m_info.get("base_url")
                k = m_info.get("api_key")
                if b_url and k:
                    return b_url, k, m_name
    except Exception as e:
        print(f"Warning: Failed reading ~/.grok/config.toml: {e}", file=sys.stderr)

    return None, None, None


def resolve_configuration(
    cli_base_url: Optional[str] = None,
    cli_api_key: Optional[str] = None,
    cli_model: Optional[str] = None,
    config_path: Optional[str] = None,
    force_official: bool = False,
) -> Tuple[Optional[str], Optional[str], str, str]:
    """
    Resolve (base_url, api_key, model, source_description) based on priority:
    1. CLI parameters (e.g. --official forces official xAI endpoint)
    2. Explicit --config file
    3. User config files: ~/.config/grok-image/config.json
    4. ~/.grok/config.toml
    5. Environment variables: XAI_API_KEY, XAI_BASE_URL, GROK_API_KEY, GROK_BASE_URL
    6. Official default: base_url = https://api.x.ai/v1
    """
    if force_official:
        base_url = OFFICIAL_BASE_URL
        config_source = "cli:force_official"
    elif cli_base_url is not None:
        cleaned = cli_base_url.strip()
        if cleaned.lower() in ("", "official", "xai", "default"):
            base_url = OFFICIAL_BASE_URL
            config_source = "cli:official_override"
        else:
            base_url = cleaned.rstrip("/")
            config_source = "cli:custom_base_url"
    else:
        base_url = None
        config_source = "defaults"

    file_base_url = None
    file_api_key = None
    file_model = None

    # 1. Custom config path passed via CLI
    if config_path:
        cp = Path(config_path).expanduser()
        data = load_json_file(cp)
        file_base_url = data.get("base_url")
        file_api_key = data.get("api_key")
        file_model = data.get("model")
        if not force_official and cli_base_url is None:
            config_source = f"file:{cp}"

    # 2. Check candidate config.json files
    if not file_base_url and not file_api_key:
        for cand in get_config_candidates():
            if cand.exists():
                data = load_json_file(cand)
                if data:
                    file_base_url = data.get("base_url")
                    file_api_key = data.get("api_key")
                    file_model = data.get("model")
                    if not force_official and cli_base_url is None:
                        config_source = f"file:{cand}"
                    break

    # 3. Check ~/.grok/config.toml
    if not file_base_url and not file_api_key:
        toml_b_url, toml_k, _ = load_grok_cli_config()
        if toml_b_url or toml_k:
            file_base_url = toml_b_url
            file_api_key = toml_k
            if not force_official and cli_base_url is None:
                config_source = "grok_cli:~/.grok/config.toml"

    # 4. Environment variables
    env_base_url = os.environ.get("XAI_BASE_URL") or os.environ.get("GROK_BASE_URL")
    env_api_key = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
    env_model = os.environ.get("GROK_IMAGE_MODEL")

    if not force_official and cli_base_url is None:
        base_url = env_base_url or file_base_url or OFFICIAL_BASE_URL
        if env_base_url or env_api_key:
            config_source = "environment_variables"

    api_key = cli_api_key or env_api_key or file_api_key or None
    model = cli_model or env_model or file_model or DEFAULT_MODEL

    # Normalise base_url
    if base_url:
        base_url = base_url.strip().rstrip("/")
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            base_url = "https://" + base_url

    return base_url, api_key, model, config_source


def mask_key(key: Optional[str]) -> str:
    if not key:
        return "(none)"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using xAI Grok Image models with custom base_url & key fallback."
    )
    parser.add_argument(
        "--prompt", "-p",
        help="Image description prompt"
    )
    parser.add_argument(
        "--filename", "-f",
        help="Output filename (e.g. image.png). Bare filenames save into system temp dir."
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Custom output directory (defaults to system temporary directory: <TEMP>/grok-image)"
    )
    parser.add_argument(
        "--model", "-m",
        help=f"Grok image model name (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--base-url",
        help=f"Custom API base_url (if not provided, falls back to config or official {OFFICIAL_BASE_URL})"
    )
    parser.add_argument(
        "--official",
        action="store_true",
        help=f"Force using official xAI endpoint ({OFFICIAL_BASE_URL})"
    )
    parser.add_argument(
        "--api-key", "-k",
        help="xAI API key (if not provided, falls back to config or XAI_API_KEY env)"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to custom configuration file (JSON)"
    )
    parser.add_argument(
        "--aspect-ratio", "-a",
        choices=["1:1", "16:9", "9:16", "4:3", "3:4"],
        help="Image aspect ratio (optional hint, if supported by upstream proxy)"
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Display resolved configuration and exit"
    )

    args = parser.parse_args()

    base_url, api_key, model, source = resolve_configuration(
        cli_base_url=args.base_url,
        cli_api_key=args.api_key,
        cli_model=args.model,
        config_path=args.config,
        force_official=args.official,
    )

    default_out_dir = Path(args.output_dir).expanduser() if args.output_dir else Path(tempfile.gettempdir()) / "grok-image"

    if args.show_config:
        is_official = base_url == OFFICIAL_BASE_URL
        mode = "Official xAI Endpoint" if is_official else f"Custom Proxy ({base_url})"
        print("=== xAI Grok Image Configuration ===")
        print(f"Mode:         {mode}")
        print(f"Base URL:     {base_url}")
        print(f"API Key:      {mask_key(api_key)}")
        print(f"Model:        {model}")
        print(f"Config Source: {source}")
        print(f"Output Dir:   {default_out_dir}")
        if args.aspect_ratio:
            print(f"Aspect Ratio: {args.aspect_ratio}")
        sys.exit(0)

    if not args.prompt:
        print("Error: --prompt is required to generate an image.", file=sys.stderr)
        print("Usage: uv run generate_image.py --prompt \"description\" [--filename out.png]", file=sys.stderr)
        sys.exit(1)

    if not api_key:
        print("Error: No xAI / Grok API Key found.\n", file=sys.stderr)
        print("未检测到 API Key。请通过以下任一方式配置：\n", file=sys.stderr)
        print("【方式 1：创建常驻自定义配置（推荐，支持中转反代）】", file=sys.stderr)
        print("  mkdir -p ~/.config/grok-image", file=sys.stderr)
        print("  cat > ~/.config/grok-image/config.json << 'EOF'", file=sys.stderr)
        print("  {", file=sys.stderr)
        print("    \"base_url\": \"https://api.your-proxy.com/v1\",", file=sys.stderr)
        print("    \"api_key\": \"sk-your-key\",", file=sys.stderr)
        print("    \"model\": \"grok-imagine-image\"", file=sys.stderr)
        print("  }", file=sys.stderr)
        print("  EOF\n", file=sys.stderr)
        print("【方式 2：使用官方环境变量】", file=sys.stderr)
        print("  Linux/macOS: export XAI_API_KEY=\"xai-...\"", file=sys.stderr)
        print("  Windows PS:  $env:XAI_API_KEY=\"xai-...\"\n", file=sys.stderr)
        print("【方式 3：CLI 单次入参】", file=sys.stderr)
        print("  uv run generate_image.py --api-key \"sk-...\" [--base-url \"https://...\"] --prompt \"...\"\n", file=sys.stderr)
        print(f"提示：若未配置自定义 base_url，脚本将自动走官方端点 ({OFFICIAL_BASE_URL})。", file=sys.stderr)
        sys.exit(1)

    import requests
    from PIL import Image as PILImage
    import io

    # Determine output directory
    target_dir = default_out_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine output filename
    if args.filename:
        user_path = Path(args.filename).expanduser()
        if user_path.is_absolute():
            output_path = user_path
        elif len(user_path.parts) > 1:
            output_path = user_path.resolve()
        else:
            output_path = target_dir / user_path.name
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = target_dir / f"grok-image-{timestamp}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare endpoint
    # xAI uses standard /images/generations (under /v1 or custom base)
    if base_url.endswith("/images/generations"):
        endpoint = base_url
    elif base_url.endswith("/v1"):
        endpoint = f"{base_url}/images/generations"
    else:
        endpoint = f"{base_url}/v1/images/generations"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "prompt": args.prompt,
        "n": 1,
        "response_format": "b64_json",
    }

    if args.aspect_ratio:
        payload["aspect_ratio"] = args.aspect_ratio

    print(f"Routing to endpoint: {endpoint}")
    print(f"Sending prompt to model '{model}'...")

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=90)
        if response.status_code != 200:
            # Fallback attempt if upstream prefers response_format: url or rejects b64_json
            if "response_format" in response.text:
                payload.pop("response_format", None)
                response = requests.post(endpoint, headers=headers, json=payload, timeout=90)

        if response.status_code != 200:
            print(f"Error from API ({response.status_code}): {response.text}", file=sys.stderr)
            sys.exit(1)

        result = response.json()
        data_list = result.get("data", [])
        if not data_list:
            print("Error: API returned no image data.", file=sys.stderr)
            sys.exit(1)

        first_item = data_list[0]
        image_obj = None

        if "b64_json" in first_item and first_item["b64_json"]:
            img_bytes = base64.b64decode(first_item["b64_json"])
            image_obj = PILImage.open(io.BytesIO(img_bytes))
        elif "url" in first_item and first_item["url"]:
            img_url = first_item["url"]
            print(f"Downloading generated image from URL: {img_url[:60]}...")
            img_resp = requests.get(img_url, timeout=60)
            img_resp.raise_for_status()
            image_obj = PILImage.open(io.BytesIO(img_resp.content))

        if not image_obj:
            print("Error: Could not extract image from response data.", file=sys.stderr)
            sys.exit(1)

        if image_obj.mode == "RGBA":
            rgb = PILImage.new("RGB", image_obj.size, (255, 255, 255))
            rgb.paste(image_obj, mask=image_obj.split()[3])
            rgb.save(str(output_path), "PNG")
        elif image_obj.mode == "RGB":
            image_obj.save(str(output_path), "PNG")
        else:
            image_obj.convert("RGB").save(str(output_path), "PNG")

        abs_path = output_path.resolve()
        print(f"\nImage successfully generated and saved: {abs_path}")

    except Exception as e:
        print(f"Error during image generation: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
