"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from promptlint import __version__
from promptlint.config import Config
from promptlint.diagnostics import Severity
from promptlint.fixer import apply_fixes
from promptlint.linter import lint_paths
from promptlint.reporters import render
from promptlint.rules import all_rules

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_USAGE = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptlint",
        description="Lint LLM prompt templates for placeholder, secret and budget problems.",
    )
    parser.add_argument("paths", nargs="*", type=Path, default=[Path(".")],
                        help="files or directories to lint (default: .)")
    parser.add_argument("--fix", action="store_true",
                        help="apply the fixes that are safe to apply automatically")
    parser.add_argument("--format", dest="fmt", choices=("text", "json", "github"),
                        default="text", help="output format (default: text)")
    parser.add_argument("--fail-on", choices=("error", "warning", "none"),
                        help="lowest severity that should exit non-zero (default: error)")
    parser.add_argument("--select", metavar="CODES",
                        help="comma-separated rule codes to run exclusively, e.g. PL001,PL004")
    parser.add_argument("--ignore", metavar="CODES",
                        help="comma-separated rule codes to skip")
    parser.add_argument("--token-budget", type=int, metavar="N",
                        help="override the PL005 token budget")
    parser.add_argument("--config", type=Path, metavar="PATH",
                        help="path to a pyproject.toml holding [tool.promptlint]")
    parser.add_argument("--list-rules", action="store_true",
                        help="print the rule reference and exit")
    parser.add_argument("--version", action="version", version=f"promptlint {__version__}")
    return parser


def _list_rules() -> int:
    width = max(len(rule.name) for rule in all_rules())
    print("code    severity  name" + " " * (width - 4) + "  description")
    for rule in all_rules():
        print(
            f"{rule.code}   {rule.severity.value:<8}  {rule.name:<{width}}  {rule.summary}"
        )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_rules:
        return _list_rules()

    paths = args.paths or [Path(".")]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"promptlint: no such file or directory: {missing[0]}", file=sys.stderr)
        return EXIT_USAGE

    config = Config.load(args.config, start=paths[0] if paths[0].is_dir() else paths[0].parent)
    if args.select:
        config.select = tuple(c.strip().upper() for c in args.select.split(",") if c.strip())
    if args.ignore:
        config.ignore = tuple(c.strip().upper() for c in args.ignore.split(",") if c.strip())
    if args.token_budget is not None:
        config.token_budget = args.token_budget
    if args.fail_on:
        config.fail_on = args.fail_on

    diagnostics, file_count = lint_paths(paths, config)

    if args.fix:
        applied, _ = apply_fixes(diagnostics)
        if applied:
            diagnostics, file_count = lint_paths(paths, config)
            if args.fmt == "text":
                print(f"Fixed {len(applied)} problem(s).")

    output = render(diagnostics, fmt=args.fmt, file_count=file_count)
    if output:
        print(output)

    return EXIT_PROBLEMS if _should_fail(diagnostics, config.fail_on) else EXIT_OK


def _should_fail(diagnostics, fail_on: str) -> bool:
    if fail_on == "none":
        return False
    threshold = Severity(fail_on).rank
    return any(d.severity.rank >= threshold for d in diagnostics)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
