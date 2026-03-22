#!/usr/bin/env python3
"""
{{PROJECT_NAME}} — {{DESCRIPTION}}
Autor: {{AUTHOR}}, {{YEAR}}
"""

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="{{PROJECT_NAME_SLUG}}",
        description="{{DESCRIPTION}}",
    )
    parser.add_argument("--version", action="version", version="0.1.0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Więcej logów")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.verbose:
        print(f"[INFO] {{PROJECT_NAME}} v0.1.0 startuje...")
    print("Cześć od {{PROJECT_NAME}}!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
