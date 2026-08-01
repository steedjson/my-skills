#!/usr/bin/env python3
"""Verify image integrity, dimensions, format, and alpha expectations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_expected(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    normalized = value.lower().replace("×", "x")
    width, height = normalized.split("x", 1)
    return int(width), int(height)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--expected-size")
    alpha = parser.add_mutually_exclusive_group()
    alpha.add_argument("--require-alpha", action="store_true")
    alpha.add_argument("--forbid-alpha", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.image).expanduser()
    failures: list[str] = []
    warnings: list[str] = []
    report: dict[str, object] = {"path": str(path.resolve()), "exists": path.is_file()}
    if not path.is_file():
        failures.append("file does not exist")
    else:
        try:
            from PIL import Image

            with Image.open(path) as probe:
                probe.verify()
            with Image.open(path) as image:
                report.update(
                    {
                        "format": image.format,
                        "mode": image.mode,
                        "width": image.width,
                        "height": image.height,
                        "file_bytes": path.stat().st_size,
                        "has_alpha_channel": "A" in image.getbands(),
                    }
                )
                expected = parse_expected(args.expected_size)
                if expected and image.size != expected:
                    failures.append(f"expected {expected[0]}x{expected[1]}, got {image.width}x{image.height}")
                has_alpha = "A" in image.getbands()
                if args.require_alpha and not has_alpha:
                    failures.append("alpha channel is required but missing")
                if args.forbid_alpha and has_alpha:
                    failures.append("alpha channel is present but forbidden")
                if has_alpha:
                    extrema = image.getchannel("A").getextrema()
                    report["alpha_extrema"] = list(extrema)
                    if args.require_alpha and extrema == (255, 255):
                        warnings.append("alpha channel exists but every pixel is fully opaque")
        except (ImportError, OSError, ValueError) as exc:
            failures.append(f"image verification failed: {exc}")

    report["failures"] = failures
    report["warnings"] = warnings
    report["passed"] = not failures
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Image: {report['path']}")
        if report.get("width"):
            print(f"Dimensions: {report['width']}x{report['height']}")
            print(f"Format/mode: {report['format']} / {report['mode']}")
        print(f"Verification: {'PASS' if report['passed'] else 'FAIL'}")
        for warning in warnings:
            print(f"WARNING: {warning}")
        for failure in failures:
            print(f"ERROR: {failure}")
    raise SystemExit(0 if not failures else 2)


if __name__ == "__main__":
    main()

