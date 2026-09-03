#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "google-genai>=1.0.0",
#     "pillow>=10.0.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""
Generate images using Gemini Image models (Gemini 3 Pro Image / Nano Banana Pro / Imagen 3).

Supports:
- Dual-channel routing: custom base_url + key (e.g. OneAPI / NewAPI / proxy) with fallback to official Google API.
- Multi-tier config resolution: CLI args > Config file > ~/.gemini/.env > Environment variables > Official fallback.
- Text-to-image and image-to-image (with --input-image).
- Multi-part thinking stream parsing (extracts final rendered image).
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple


DEFAULT_MODEL = "gemini-3.1-flash-image"
DEFAULT_RESOLUTION = "1K"


def get_config_candidates() -> list:
    """Return platform-aware candidate paths for configuration files."""
    candidates = []
    # Windows native AppData
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(Path(appdata) / "gemini-banana" / "config.json")

    # Cross-platform home directory configs
    candidates.extend([
        Path.home() / ".config" / "gemini-banana" / "config.json",
        Path.home() / ".gemini" / ".env",
        Path.home() / ".gemini-banana.json",
    ])
    return candidates


def load_env_file(filepath: Path) -> dict:
    """Parse a simple .env file without requiring external dependencies."""
    env_vars = {}
    if not filepath.exists() or not filepath.is_file():
        return env_vars

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    env_vars[key] = val
    except Exception as e:
        print(f"Warning: Failed reading {filepath}: {e}", file=sys.stderr)
    return env_vars


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


def resolve_configuration(
    cli_base_url: Optional[str] = None,
    cli_api_key: Optional[str] = None,
    cli_model: Optional[str] = None,
    config_path: Optional[str] = None,
    force_official: bool = False,
) -> Tuple[Optional[str], Optional[str], str, str]:
    """
    Resolve (base_url, api_key, model, source_description) based on priority:
    1. CLI parameters (e.g. --official forces base_url=None)
    2. Explicit --config file
    3. User config files: ~/.config/gemini-banana/config.json, ~/.gemini/.env
    4. Environment variables
    5. Official default (base_url=None)
    """
    if force_official:
        base_url = None
        config_source = "cli:force_official"
    elif cli_base_url is not None:
        cleaned = cli_base_url.strip()
        if cleaned.lower() in ("", "official", "google", "none"):
            base_url = None
            config_source = "cli:official_override"
        else:
            base_url = cleaned
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
        if cp.suffix == ".json":
            data = load_json_file(cp)
            file_base_url = data.get("base_url")
            file_api_key = data.get("api_key")
            file_model = data.get("model")
            if not force_official and cli_base_url is None:
                config_source = f"file:{cp}"
        else:
            data = load_env_file(cp)
            file_base_url = data.get("GEMINI_BASE_URL") or data.get("GOOGLE_GEMINI_BASE_URL")
            file_api_key = data.get("GEMINI_API_KEY") or data.get("GOOGLE_API_KEY")
            file_model = data.get("GEMINI_IMAGE_MODEL")
            if not force_official and cli_base_url is None:
                config_source = f"env_file:{cp}"

    # 2. Check candidate files if not resolved
    if not file_base_url and not file_api_key:
        for cand in get_config_candidates():
            if cand.exists():
                if cand.suffix == ".json":
                    data = load_json_file(cand)
                    if data:
                        file_base_url = data.get("base_url")
                        file_api_key = data.get("api_key")
                        file_model = data.get("model")
                        if not force_official and cli_base_url is None:
                            config_source = f"file:{cand}"
                        break
                elif cand.name == ".env":
                    data = load_env_file(cand)
                    if data:
                        file_base_url = data.get("GEMINI_BASE_URL") or data.get("GOOGLE_GEMINI_BASE_URL")
                        file_api_key = data.get("GEMINI_API_KEY") or data.get("GOOGLE_API_KEY")
                        file_model = data.get("GEMINI_IMAGE_MODEL")
                        if not force_official and cli_base_url is None:
                            config_source = f"env_file:{cand}"
                        break

    # 3. Environment variables
    env_base_url = os.environ.get("GEMINI_BASE_URL") or os.environ.get("GOOGLE_GEMINI_BASE_URL")
    env_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    env_model = os.environ.get("GEMINI_IMAGE_MODEL")

    if not force_official and cli_base_url is None:
        base_url = env_base_url or file_base_url or None

    api_key = cli_api_key or env_api_key or file_api_key or None
    model = cli_model or env_model or file_model or DEFAULT_MODEL

    # Normalise empty string base_url to None (None => official Google endpoint)
    if base_url is not None:
        base_url = base_url.strip()
        if not base_url or base_url.lower() in ("official", "none", "google"):
            base_url = None

    return base_url, api_key, model, config_source


def mask_key(key: Optional[str]) -> str:
    if not key:
        return "(none)"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def main():
    parser = argparse.ArgumentParser(
        description="Generate images using Gemini Banana / Nano Banana Pro with custom base_url & key fallback."
    )
    parser.add_argument(
        "--prompt", "-p",
        help="Image description prompt"
    )
    parser.add_argument(
        "--filename", "-f",
        help="Output filename (e.g. cat.png or /path/to/custom.png). Bare filenames save into system temp dir."
    )
    parser.add_argument(
        "--output-dir", "-o",
        help="Custom output directory (defaults to system temporary directory: <TEMP>/gemini-banana)"
    )
    parser.add_argument(
        "--input-image", "-i",
        help="Optional input image path for image-to-image editing"
    )
    parser.add_argument(
        "--resolution", "-r",
        choices=["1K", "2K", "4K"],
        default=DEFAULT_RESOLUTION,
        help=f"Output resolution (default: {DEFAULT_RESOLUTION})"
    )
    parser.add_argument(
        "--aspect-ratio", "-a",
        choices=["1:1", "16:9", "9:16", "4:3", "3:4"],
        help="Image aspect ratio (e.g. 1:1, 16:9, 4:3)"
    )
    parser.add_argument(
        "--model", "-m",
        help=f"Gemini image model name (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--base-url",
        help="Custom API base_url (if not provided, falls back to config or official Google API)"
    )
    parser.add_argument(
        "--official",
        action="store_true",
        help="Force using official Google API endpoint (ignores configured custom base_url)"
    )
    parser.add_argument(
        "--api-key", "-k",
        help="Gemini API key (if not provided, falls back to config or GEMINI_API_KEY env)"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to custom configuration file (JSON or .env)"
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

    if args.show_config:
        import tempfile
        default_out_dir = Path(args.output_dir).expanduser() if args.output_dir else Path(tempfile.gettempdir()) / "gemini-banana"
        mode = f"Custom Proxy ({base_url})" if base_url else "Official Google GenAI Endpoint"
        print("=== Gemini Banana Image Configuration ===")
        print(f"Mode:         {mode}")
        print(f"Base URL:     {base_url or '(official default)'}")
        print(f"API Key:      {mask_key(api_key)}")
        print(f"Model:        {model}")
        print(f"Config Source: {source}")
        print(f"Output Dir:   {default_out_dir}")
        print(f"Resolution:   {args.resolution}")
        if args.aspect_ratio:
            print(f"Aspect Ratio: {args.aspect_ratio}")
        sys.exit(0)

    if not args.prompt:
        print("Error: --prompt is required to generate an image.", file=sys.stderr)
        print("Usage: uv run generate_image.py --prompt \"description\" [--filename out.png]", file=sys.stderr)
        sys.exit(1)

    if not api_key:
        print("Error: No Gemini API Key found.\n", file=sys.stderr)
        print("未检测到 API Key。请通过以下任一方式配置：\n", file=sys.stderr)
        print("【方式 1：创建常驻自定义配置（推荐，支持中转反代）】", file=sys.stderr)
        print("  mkdir -p ~/.config/gemini-banana", file=sys.stderr)
        print("  cat > ~/.config/gemini-banana/config.json << 'EOF'", file=sys.stderr)
        print("  {", file=sys.stderr)
        print("    \"base_url\": \"https://api.your-proxy.com\",", file=sys.stderr)
        print("    \"api_key\": \"sk-your-key\",", file=sys.stderr)
        print("    \"model\": \"gemini-3-pro-image-preview\"", file=sys.stderr)
        print("  }", file=sys.stderr)
        print("  EOF\n", file=sys.stderr)
        print("【方式 2：使用官方端点环境变量】", file=sys.stderr)
        print("  Linux/macOS: export GEMINI_API_KEY=\"AIzaSy...\"", file=sys.stderr)
        print("  Windows PS:  $env:GEMINI_API_KEY=\"AIzaSy...\"\n", file=sys.stderr)
        print("【方式 3：CLI 单次入参】", file=sys.stderr)
        print("  uv run generate_image.py --api-key \"sk-...\" [--base-url \"https://...\"] --prompt \"...\"\n", file=sys.stderr)
        print("提示：若仅配置 api_key 而不配置 base_url，脚本将自动走 Google 官方直连端点。", file=sys.stderr)
        sys.exit(1)

    # Lazy imports after argument checks
    from google import genai
    from google.genai import types
    from PIL import Image as PILImage
    import io
    import base64
    import tempfile

    # Initialise client with custom base_url if present
    client_kwargs = {"api_key": api_key}
    if base_url:
        print(f"Routing to custom base_url: {base_url}")
        client_kwargs["http_options"] = types.HttpOptions(base_url=base_url)
    else:
        print("Routing to official Google GenAI endpoint")

    client = genai.Client(**client_kwargs)

    # Determine output directory (default: system temp directory to keep user repo clean)
    if args.output_dir:
        target_dir = Path(args.output_dir).expanduser()
    else:
        target_dir = Path(tempfile.gettempdir()) / "gemini-banana"

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
        output_path = target_dir / f"gemini-image-{timestamp}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Handle input image if provided
    input_image = None
    output_resolution = args.resolution
    if args.input_image:
        try:
            input_image = PILImage.open(args.input_image)
            print(f"Loaded input image for editing: {args.input_image}")
            # Auto-detect resolution if user left default
            if args.resolution == DEFAULT_RESOLUTION:
                w, h = input_image.size
                max_dim = max(w, h)
                if max_dim >= 3000:
                    output_resolution = "4K"
                elif max_dim >= 1500:
                    output_resolution = "2K"
                else:
                    output_resolution = "1K"
                print(f"Auto-detected resolution from input image: {output_resolution} ({w}x{h})")
        except Exception as e:
            print(f"Error loading input image '{args.input_image}': {e}", file=sys.stderr)
            sys.exit(1)

    # Assemble request contents
    if input_image:
        contents = [input_image, args.prompt]
    else:
        contents = args.prompt

    # Build image configuration
    image_config_args = {}
    if output_resolution:
        image_config_args["image_size"] = output_resolution
    if args.aspect_ratio:
        image_config_args["aspect_ratio"] = args.aspect_ratio

    gen_config = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(**image_config_args) if image_config_args else None
    )

    print(f"Sending prompt to model '{model}' (Resolution: {output_resolution})...")

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=gen_config,
        )

        last_image = None

        # Parse response parts, taking care of thinking chain parts and extracting the last valid image
        for i, part in enumerate(response.parts):
            if part.text is not None:
                text_preview = part.text.strip()
                if text_preview:
                    print(f"[Model Note]: {text_preview[:120]}{'...' if len(text_preview) > 120 else ''}")
            else:
                try:
                    # 1. Try SDK native as_image()
                    img = getattr(part, "as_image", None)
                    if callable(img):
                        img_obj = part.as_image()
                        if isinstance(img_obj, PILImage.Image):
                            last_image = img_obj
                            continue

                    # 2. Try inline_data
                    inline = getattr(part, "inline_data", None)
                    if inline is not None and getattr(inline, "data", None):
                        raw_data = inline.data
                        if isinstance(raw_data, str):
                            raw_data = base64.b64decode(raw_data)
                        img_obj = PILImage.open(io.BytesIO(raw_data))
                        last_image = img_obj
                except Exception as ex:
                    print(f"Warning: Failed parsing image part {i}: {ex}", file=sys.stderr)

        if last_image is None:
            print("Error: No valid image was found in the API response.", file=sys.stderr)
            sys.exit(1)

        # Ensure image is saved cleanly
        if last_image.mode == "RGBA":
            rgb = PILImage.new("RGB", last_image.size, (255, 255, 255))
            rgb.paste(last_image, mask=last_image.split()[3])
            rgb.save(str(output_path), "PNG")
        elif last_image.mode == "RGB":
            last_image.save(str(output_path), "PNG")
        else:
            last_image.convert("RGB").save(str(output_path), "PNG")

        abs_path = output_path.resolve()
        print(f"\nImage successfully generated and saved: {abs_path}")

    except Exception as e:
        print(f"Error during image generation: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
