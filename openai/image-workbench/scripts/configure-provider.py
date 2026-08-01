#!/usr/bin/env python3
"""Show and validate the effective provider without revealing credentials."""

from __future__ import annotations

import argparse

from _common import WorkbenchError, discover_models, fail, print_json, resolve_provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", help="Override the Base URL for this invocation")
    parser.add_argument("--api-key-env", help="Read the credential from this environment variable")
    parser.add_argument("--codex-home", help="Override the Codex home used for config discovery")
    parser.add_argument("--check", action="store_true", help="Probe official docs and the provider model endpoint")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        config = resolve_provider(
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            codex_home=args.codex_home,
        )
        result = {"configuration": config.public_dict()}
        if args.check:
            result["diagnostics"] = discover_models(config, timeout=args.timeout)
        if args.json:
            print_json(result)
            return

        public = config.public_dict()
        print(f"Base URL: {public['base_url']}")
        print(f"Base URL source: {public['base_source']}")
        print(f"Provider: {public['provider_name']} ({public['provider_category']})")
        print(f"API key configured: {'yes' if public['api_key_configured'] else 'no'}")
        print(f"API key source: {public['key_source']}")
        if public["provider_category"] == "third_party":
            print("Privacy: prompts, images, and the selected credential are sent to this third party.")
        if args.check:
            diagnostics = result["diagnostics"]
            print(f"Official model source: {diagnostics['official_source']}")
            print(
                "Official models available from provider: "
                + (", ".join(diagnostics["official_available_from_provider"]) or "none confirmed")
            )
            if diagnostics["provider_discovery_error"]:
                print(f"Provider discovery: failed ({diagnostics['provider_discovery_error']})")
            else:
                print(f"Provider model endpoint: {diagnostics['provider_models_endpoint']}")
    except WorkbenchError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()

