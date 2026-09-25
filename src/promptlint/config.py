"""Configuration, read from ``[tool.promptlint]`` in pyproject.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_INPUT_VARIABLES = (
    "user_input", "user_message", "user_query", "query", "question", "input",
    "text", "content", "document", "documents", "context", "message", "body",
    "search_results", "retrieved", "chunk", "chunks", "comment", "email",
)


@dataclass
class Config:
    """Everything the linter can be tuned with."""

    select: tuple[str, ...] | None = None
    ignore: tuple[str, ...] = ()
    token_budget: int = 4000
    tokenizer: str = "heuristic"
    user_input_variables: tuple[str, ...] = DEFAULT_USER_INPUT_VARIABLES
    declared_variables: tuple[str, ...] = ()
    fail_on: str = "error"
    source: Path | None = field(default=None, compare=False)

    def enabled(self, code: str) -> bool:
        if code in self.ignore:
            return False
        return self.select is None or code in self.select

    @classmethod
    def load(cls, explicit: Path | None = None, start: Path | None = None) -> Config:
        """Load config from ``explicit``, or the nearest pyproject.toml above ``start``."""
        path = explicit or _find_pyproject(start or Path.cwd())
        if path is None or not path.is_file():
            return cls()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return cls()

        table = data.get("tool", {}).get("promptlint", {})
        if not isinstance(table, dict):
            return cls(source=path)

        defaults = cls()
        select = table.get("select")
        return cls(
            select=tuple(select) if select else None,
            ignore=tuple(table.get("ignore", ())),
            token_budget=int(table.get("token_budget", defaults.token_budget)),
            tokenizer=str(table.get("tokenizer", defaults.tokenizer)),
            user_input_variables=tuple(
                table.get("user_input_variables", defaults.user_input_variables)
            ),
            declared_variables=tuple(table.get("declared_variables", ())),
            fail_on=str(table.get("fail_on", defaults.fail_on)),
            source=path,
        )


def _find_pyproject(start: Path) -> Path | None:
    start = start.resolve()
    for directory in [start, *start.parents]:
        candidate = directory / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None
