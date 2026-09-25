"""The autofix engine, including its refusal to touch text that moved."""

from __future__ import annotations

from dataclasses import replace

from promptlint.config import Config
from promptlint.fixer import apply_fixes
from promptlint.linter import lint_file


def test_trailing_whitespace_is_stripped(tmp_path):
    path = tmp_path / "p.md"
    path.write_text("one  \ntwo\t\nthree\n")
    applied, skipped = apply_fixes(lint_file(path, Config()))
    assert len(applied) == 2 and not skipped
    assert path.read_text() == "one\ntwo\nthree\n"


def test_literal_braces_are_escaped_and_then_format(tmp_path):
    path = tmp_path / "p.md"
    path.write_text('Return {"a": 1} for {name}\n')
    apply_fixes(lint_file(path, Config()))
    fixed = path.read_text()
    assert fixed == 'Return {{"a": 1}} for {name}\n'
    assert fixed.format(name="x") == 'Return {"a": 1} for x\n'


def test_multiple_fixes_on_one_line_apply_right_to_left(tmp_path):
    path = tmp_path / "p.md"
    path.write_text('{"a": 1} and {"b": 2}\n')
    applied, skipped = apply_fixes(lint_file(path, Config()))
    assert len(applied) == 2 and not skipped
    assert path.read_text() == '{{"a": 1}} and {{"b": 2}}\n'


def test_fix_is_skipped_when_the_text_moved(tmp_path):
    path = tmp_path / "p.md"
    path.write_text("one  \n")
    (diagnostic,) = [d for d in lint_file(path, Config()) if d.fixable]
    stale = replace(diagnostic, fix=replace(diagnostic.fix, column=99))
    applied, skipped = apply_fixes([stale])
    assert not applied and skipped == [stale]
    assert path.read_text() == "one  \n"


def test_python_files_are_left_alone(tmp_path):
    path = tmp_path / "a.py"
    original = 'PROMPT = """one  \ntwo"""\n'
    path.write_text(original)
    applied, _ = apply_fixes(lint_file(path, Config()))
    assert not applied
    assert path.read_text() == original


def test_fixing_is_idempotent(tmp_path):
    path = tmp_path / "p.md"
    path.write_text('Return {"a": 1}  \n')
    apply_fixes(lint_file(path, Config()))
    first = path.read_text()
    apply_fixes(lint_file(path, Config()))
    assert path.read_text() == first
