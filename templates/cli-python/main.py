#!/usr/bin/env python3
"""
{{PROJECT_NAME}} — {{DESCRIPTION}}
Autor: {{AUTHOR}}, {{YEAR}}
"""

import argparse
import sys

try:
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
except ImportError:
    class Console:
        def print(self, *a, **kw): print(*a)
    console = Console()
    Panel = None


VERSION = "0.1.0"


def cmd_run(args):
    """Domyślna komenda."""
    console.print(f"[bold green]{{PROJECT_NAME}}[/] v{VERSION}")
    console.print(f"{{DESCRIPTION}}")


def cmd_version(args):
    print(f"{{PROJECT_NAME}} v{VERSION}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="{{PROJECT_NAME_SLUG}}",
        description="{{DESCRIPTION}}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", "-V", action="store_true", help="Pokaż wersję")
    parser.add_argument("--verbose", "-v", action="store_true", help="Więcej logów")

    sub = parser.add_subparsers(dest="command", metavar="KOMENDA")

    run_p = sub.add_parser("run", help="Uruchom główną logikę")
    run_p.add_argument("input", nargs="?", help="Opcjonalne wejście")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.version:
        cmd_version(args)
        return 0

    if args.command == "run" or args.command is None:
        cmd_run(args)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
