"""The diagnostic record every rule produces."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"

    @property
    def rank(self) -> int:
        return {"error": 2, "warning": 1}[self.value]


@dataclass(frozen=True)
class Diagnostic:
    """One problem found in one prompt, anchored to a position in a file."""

    code: str
    message: str
    path: str
    line: int
    column: int
    severity: Severity
    hint: str | None = None
    prompt_name: str | None = None

    @property
    def sort_key(self) -> tuple[str, int, int, str]:
        return (self.path, self.line, self.column, self.code)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "severity": self.severity.value,
            "hint": self.hint,
            "prompt": self.prompt_name,
        }
