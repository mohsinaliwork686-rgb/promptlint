"""Run the rules over files."""

from __future__ import annotations

from pathlib import Path

from promptlint.config import Config
from promptlint.diagnostics import Diagnostic
from promptlint.rules import RuleContext, all_rules
from promptlint.sources import PromptSource, discover, extract


def lint_prompt(prompt: PromptSource, config: Config) -> list[Diagnostic]:
    ctx = RuleContext(config=config)
    found: list[Diagnostic] = []
    for rule in all_rules():
        if not config.enabled(rule.code):
            continue
        found.extend(rule.check(prompt, ctx))
    return found


def lint_file(path: Path, config: Config) -> list[Diagnostic]:
    found: list[Diagnostic] = []
    for prompt in extract(path):
        found.extend(lint_prompt(prompt, config))
    return sorted(found, key=lambda d: d.sort_key)


def lint_paths(paths: list[Path], config: Config) -> tuple[list[Diagnostic], int]:
    """Lint every discovered file. Returns the diagnostics and the file count."""
    files = discover(paths)
    found: list[Diagnostic] = []
    for path in files:
        found.extend(lint_file(path, config))
    return sorted(found, key=lambda d: d.sort_key), len(files)
