#!/usr/bin/env python3
"""Edit one or more images through the active OpenAI-compatible Image API."""

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
    encode_multipart,
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
    if out.suffix.lower() in {".jpg", ".jpeg"}:
        return "jpeg"
    if out.suffix.lower() == ".webp":
        return "webp"
    return "png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", action="append", required=True, help="Input image; repeat for multiple images")
    parser.add_argument("--mask")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--model", default="auto")
    parser.add_argument("--size", default="auto", help="Final size: auto or WIDTHxHEIGHT")
    parser.add_argument("--fit", choices=("crop", "contain", "stretch", "none"), default="crop")
    parser.add_argument("--quality", choices=("low", "medium", "high", "auto"), default="auto")
    parser.add_argument("--background", choices=("opaque", "transparent", "auto"), default="auto")
    parser.add_argument("--output-format", choices=("png", "jpeg", "webp", "auto"), default="auto")
    parser.add_argument("--input-fidelity", choices=("low", "high", "auto"), default="auto")
    parser.add_argument("--out")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    parser.add_argument("--codex-home")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        inputs = [Path(value).expanduser() for value in args.image]
        missing = [str(path) for path in inputs if not path.is_file()]
        if missing:
            raise WorkbenchError("Input image not found: " + ", ".join(missing))
        mask = Path(args.mask).expanduser() if args.mask else None
        if mask and not mask.is_file():
            raise WorkbenchError(f"Mask not found: {mask}")

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
        if model == "gpt-image-2" and args.input_fidelity != "auto":
            raise WorkbenchError("gpt-image-2 always uses high input fidelity; omit --input-fidelity")
        plan = normalize_size(args.size, model, args.fit)
        out = Path(args.out).expanduser() if args.out else default_output_path("edited")
        fmt = output_format(args, out)
        if args.background == "transparent" and fmt not in {"png", "webp"}:
            raise WorkbenchError("Transparent output requires PNG or WebP")

        fields = {
            "model": model,
            "prompt": args.prompt,
            "n": "1",
            "size": str(plan["api_size"]),
            "quality": args.quality,
            "background": args.background,
            "output_format": fmt,
        }
        if args.input_fidelity != "auto":
            fields["input_fidelity"] = args.input_fidelity
        image_field = "image" if len(inputs) == 1 else "image[]"
        files: list[tuple[str, Path]] = [(image_field, path) for path in inputs]
        if mask:
            files.append(("mask", mask))

        public_plan = {
            "operation": "edit",
            "provider": config.public_dict(),
            "model": model,
            "size": plan,
            "quality": args.quality,
            "background": args.background,
            "output_format": fmt,
            "input_count": len(inputs),
            "mask_supplied": bool(mask),
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
                endpoint="images/edits",
                method="POST",
                body_factory=lambda: encode_multipart(fields, files),
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

