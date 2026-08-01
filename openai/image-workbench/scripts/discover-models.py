#!/usr/bin/env python3
"""Discover official image models and intersect them with the active provider."""

from __future__ import annotations

import argparse

from _common import WorkbenchError, discover_models, fail, print_json, resolve_provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    parser.add_argument("--codex-home")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        config = resolve_provider(
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            codex_home=args.codex_home,
        )
        result = discover_models(config, timeout=args.timeout)
        if args.json:
            print_json(result)
            return
        print("Officially documented image models:")
        for model in result["official_models"]:
            print(f"  - {model}")
        print(f"Source: {result['official_source']}")
        if result["official_warning"]:
            print(f"Official discovery warning: {result['official_warning']}")
        print("Available from configured provider:")
        available = result["official_available_from_provider"]
        print("\n".join(f"  - {model}" for model in available) if available else "  - none confirmed")
        print("Official but unavailable from configured provider:")
        unavailable = result["official_unavailable_from_provider"]
        print("\n".join(f"  - {model}" for model in unavailable) if unavailable else "  - none")
        print("Provider-only image-like models (capabilities unknown):")
        provider_only = result["provider_only_image_like_models"]
        print("\n".join(f"  - {model}" for model in provider_only) if provider_only else "  - none")
        if result["provider_discovery_error"]:
            print(f"Provider discovery error: {result['provider_discovery_error']}")
    except WorkbenchError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()

