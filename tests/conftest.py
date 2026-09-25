from __future__ import annotations

from pathlib import Path

import pytest

from promptlint.config import Config
from promptlint.linter import lint_file, lint_prompt
from promptlint.sources import PromptSource


@pytest.fixture
def config() -> Config:
    return Config()


@pytest.fixture
def check(config):
    """Lint a bare template string and return the diagnostic codes found."""

    def _check(text: str, *, declared=None, kind: str = "text", cfg: Config | None = None):
        prompt = PromptSource(
            path=Path("memory.md"),
            text=text,
            declared=None if declared is None else frozenset(declared),
            kind=kind,
        )
        return lint_prompt(prompt, cfg or config)

    return _check


@pytest.fixture
def lint_text(tmp_path, config):
    """Write a file and lint it, returning the diagnostics."""

    def _lint(name: str, content: str, cfg: Config | None = None):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path, lint_file(path, cfg or config)

    return _lint


def codes(diagnostics) -> list[str]:
    return [d.code for d in diagnostics]
