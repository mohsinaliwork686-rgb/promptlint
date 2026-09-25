"""Apply the autofixes a diagnostic carries, position-verified so it cannot corrupt a file."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from promptlint.diagnostics import Diagnostic


def apply_fixes(diagnostics: list[Diagnostic]) -> tuple[list[Diagnostic], list[Diagnostic]]:
    """Apply every fixable diagnostic. Returns ``(applied, skipped)``.

    A fix is skipped when its ``old`` text is no longer at the recorded position,
    which keeps a mis-mapped offset from damaging the file.
    """
    by_path: dict[str, list[Diagnostic]] = defaultdict(list)
    for diagnostic in diagnostics:
        if diagnostic.fixable:
            by_path[diagnostic.path].append(diagnostic)

    applied: list[Diagnostic] = []
    skipped: list[Diagnostic] = []

    for raw_path, items in by_path.items():
        path = Path(raw_path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            skipped.extend(items)
            continue

        changed = False
        # Right to left, bottom to top, so earlier offsets stay valid.
        for diagnostic in sorted(
            items, key=lambda d: (d.fix.line, d.fix.column), reverse=True
        ):
            fix = diagnostic.fix
            index = fix.line - 1
            if not 0 <= index < len(lines):
                skipped.append(diagnostic)
                continue
            line = lines[index]
            start = fix.column - 1
            if line[start : start + len(fix.old)] != fix.old:
                skipped.append(diagnostic)
                continue
            lines[index] = line[:start] + fix.new + line[start + len(fix.old) :]
            applied.append(diagnostic)
            changed = True

        if changed:
            path.write_text("".join(lines), encoding="utf-8")

    return applied, skipped
