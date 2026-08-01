#!/usr/bin/env python3
"""Generate one image through the active OpenAI-compatible Image API."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from _common import (
    WorkbenchError,
    choose_model,
    default_output_path,
    discover_models,
    fail,
    normalize_size,
    postprocess_image,
    print_json,
    request_json_with_path_probe,
    resolve_provider,
    save_image_response,
)


def output_format(args: argparse.Namespace, out: Path) -> str:
    if args.output_format != "auto":
        return args.output_format
    suffix = out.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "jpeg"
    if suffix == ".webp":
        return "webp"
    return "png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="auto")
    parser.add_argument("--size", default="auto", help="Final size: auto or WIDTHxHEIGHT")
    parser.add_argument("--fit", choices=("crop", "contain", "stretch", "none"), default="crop")
    parser.add_argument("--quality", choices=("low", "medium", "high", "auto"), default="auto")
    parser.add_argument("--background", choices=("opaque", "transparent", "auto"), default="auto")
    parser.add_argument("--output-format", choices=("png", "jpeg", "webp", "auto"), default="auto")
    parser.add_argument("--compression", type=int, choices=range(0, 101), metavar="0-100")
    parser.add_argument("--moderation", choices=("auto", "low"), default="auto")
    parser.add_argument("--out")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    parser.add_argument("--codex-home")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        config = resolve_provider(
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            codex_home=args.codex_home,
        )
        if not config.api_key:
            raise WorkbenchError(
                "No API key was found in the selected environment variable, OPENAI_API_KEY, or Codex auth.json"
            )
        discovery = discover_models(config, timeout=min(args.timeout, 30))
        model = choose_model(discovery, args.model, require_transparency=args.background == "transparent")
        plan = normalize_size(args.size, model, args.fit)
        out = Path(args.out).expanduser() if args.out else default_output_path("generated")
        fmt = output_format(args, out)
        if args.background == "transparent" and fmt not in {"png", "webp"}:
            raise WorkbenchError("Transparent output requires PNG or WebP")

        payload: dict[str, object] = {
            "model": model,
            "prompt": args.prompt,
            "n": 1,
            "size": plan["api_size"],
            "quality": args.quality,
            "background": args.background,
            "output_format": fmt,
            "moderation": args.moderation,
        }
        if args.compression is not None:
            if fmt not in {"jpeg", "webp"}:
                raise WorkbenchError("Compression applies only to JPEG or WebP")
            payload["output_compression"] = args.compression

        public_plan = {
            "operation": "generate",
            "provider": config.public_dict(),
            "model": model,
            "size": plan,
            "quality": args.quality,
            "background": args.background,
            "output_format": fmt,
            "output": str(out.resolve()),
            "model_discovery": {
                "official_source": discovery["official_source"],
                "provider_models_endpoint": discovery["provider_models_endpoint"],
                "provider_discovery_error": discovery["provider_discovery_error"],
            },
        }
        if args.dry_run:
            print_json(public_plan)
            return

        out.parent.mkdir(parents=True, exist_ok=True)
        temp_handle = tempfile.NamedTemporaryFile(
            prefix=f".{out.stem}-source-", suffix=f".{fmt}", dir=out.parent, delete=False
        )
        temp_path = Path(temp_handle.name)
        temp_handle.close()
        try:
            response, endpoint = request_json_with_path_probe(
                config=config,
                endpoint="images/generations",
                method="POST",
                payload=payload,
                timeout=args.timeout,
            )
            save_image_response(response, temp_path, timeout=60)
            transform = postprocess_image(temp_path, out, args.size, args.fit)
            public_plan["endpoint"] = endpoint
            public_plan["postprocess"] = transform
            public_plan["completed"] = True
            print_json(public_plan)
        finally:
            if temp_path.exists() and out.exists():
                os.unlink(temp_path)
    except WorkbenchError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()

