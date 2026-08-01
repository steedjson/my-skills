#!/usr/bin/env python3
"""Map an exact requested size to a model-compatible API size."""

from __future__ import annotations

import argparse

from _common import WorkbenchError, fail, normalize_size, print_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requested", required=True, help="auto or WIDTHxHEIGHT")
    parser.add_argument("--model", required=True)
    parser.add_argument("--fit", choices=("crop", "contain", "stretch", "none"), default="crop")
    args = parser.parse_args()
    try:
        print_json(normalize_size(args.requested, args.model, args.fit))
    except WorkbenchError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()

