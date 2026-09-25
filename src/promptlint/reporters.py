"""Turn diagnostics into something a human or a CI runner can read."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable

from promptlint.diagnostics import Diagnostic, Severity

_RESET = "\033[0m"
_COLORS = {
    "error": "\033[31m",
    "warning": "\033[33m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
}


def supports_color(stream) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def render(
    diagnostics: list[Diagnostic],
    *,
    fmt: str,
    file_count: int,
    stream=None,
    color: bool | None = None,
) -> str:
    stream = stream or sys.stdout
    if fmt == "json":
        return json.dumps(
            {
                "files_scanned": file_count,
                "diagnostics": [d.to_dict() for d in diagnostics],
                "summary": _counts(diagnostics),
            },
            indent=2,
        )
    if fmt == "github":
        return "\n".join(_github(d) for d in diagnostics)
    use_color = supports_color(stream) if color is None else color
    return _text(diagnostics, file_count, use_color)


def _counts(diagnostics: Iterable[Diagnostic]) -> dict[str, int]:
    diagnostics = list(diagnostics)
    return {
        "errors": sum(1 for d in diagnostics if d.severity is Severity.ERROR),
        "warnings": sum(1 for d in diagnostics if d.severity is Severity.WARNING),
        "fixable": sum(1 for d in diagnostics if d.fixable),
    }


def _github(diagnostic: Diagnostic) -> str:
    level = "error" if diagnostic.severity is Severity.ERROR else "warning"
    message = f"{diagnostic.code} {diagnostic.message}"
    if diagnostic.hint:
        message += f" — {diagnostic.hint}"
    message = message.replace("\n", "%0A").replace("\r", "")
    return (
        f"::{level} file={diagnostic.path},line={diagnostic.line},"
        f"col={diagnostic.column},title=promptlint {diagnostic.code}::{message}"
    )


def _text(diagnostics: list[Diagnostic], file_count: int, color: bool) -> str:
    def paint(text: str, key: str) -> str:
        return f"{_COLORS[key]}{text}{_RESET}" if color else text

    lines: list[str] = []
    for diagnostic in diagnostics:
        location = f"{diagnostic.path}:{diagnostic.line}:{diagnostic.column}"
        severity = diagnostic.severity.value
        lines.append(
            f"{paint(location, 'bold')}: "
            f"{paint(severity, severity)} "
            f"{paint(diagnostic.code, 'cyan')} {diagnostic.message}"
        )
        if diagnostic.hint:
            lines.append(paint(f"    hint: {diagnostic.hint}", "dim"))

    counts = _counts(diagnostics)
    if not diagnostics:
        message = f"All clear — {_plural(file_count, 'file')} scanned, no problems."
        lines.append(paint(message, "dim"))
        return "\n".join(lines)

    parts = []
    if counts["errors"]:
        parts.append(paint(_plural(counts["errors"], "error"), "error"))
    if counts["warnings"]:
        parts.append(paint(_plural(counts["warnings"], "warning"), "warning"))
    summary = f"\nFound {' and '.join(parts)} in {_plural(file_count, 'file')} scanned."
    if counts["fixable"]:
        summary += paint(f" {counts['fixable']} fixable with --fix.", "dim")
    lines.append(summary)
    return "\n".join(lines)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"
