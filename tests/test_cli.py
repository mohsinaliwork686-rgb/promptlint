"""End-to-end behaviour of the command line."""

from __future__ import annotations

import json

import pytest

from promptlint.cli import main


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.promptlint]\ntoken_budget = 4000\n")
    return tmp_path


def test_clean_tree_exits_zero(project, capsys):
    (project / "p.md").write_text("Hello {name}\n")
    assert main([str(project)]) == 0
    assert "All clear" in capsys.readouterr().out


def test_errors_exit_one(project, capsys):
    (project / "p.md").write_text('Return {"a": 1}\n')
    assert main([str(project)]) == 1
    assert "PL001" in capsys.readouterr().out


def test_fail_on_none_always_exits_zero(project):
    (project / "p.md").write_text('Return {"a": 1}\n')
    assert main([str(project), "--fail-on", "none"]) == 0


def test_fail_on_warning_catches_warnings(project):
    (project / "p.md").write_text("Hello {name}  \n")
    assert main([str(project)]) == 0
    assert main([str(project), "--fail-on", "warning"]) == 1


def test_json_output_is_parseable(project, capsys):
    (project / "p.md").write_text('Return {"a": 1}\n')
    main([str(project), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["errors"] == 1
    assert payload["diagnostics"][0]["code"] == "PL001"
    assert payload["files_scanned"] == 1


def test_github_format_emits_annotations(project, capsys):
    (project / "p.md").write_text('Return {"a": 1}\n')
    main([str(project), "--format", "github"])
    out = capsys.readouterr().out
    assert out.startswith("::error file=")
    assert "title=promptlint PL001" in out
    assert "\n" not in out.strip()


def test_fix_rewrites_the_file(project, capsys):
    path = project / "p.md"
    path.write_text("Hello {name}  \n")
    main([str(project), "--fix", "--fail-on", "none"])
    assert path.read_text() == "Hello {name}\n"
    assert "Fixed 1 problem" in capsys.readouterr().out


def test_select_and_ignore_flags(project, capsys):
    (project / "p.md").write_text('Return {"a": 1}  \n')
    main([str(project), "--select", "pl007", "--fail-on", "none"])
    out = capsys.readouterr().out
    assert "PL007" in out and "PL001" not in out

    main([str(project), "--ignore", "PL001", "--fail-on", "none"])
    out = capsys.readouterr().out
    assert "PL007" in out and "PL001" not in out


def test_token_budget_override(project, capsys):
    (project / "p.md").write_text("word " * 200)
    main([str(project), "--token-budget", "10", "--fail-on", "none"])
    assert "PL005" in capsys.readouterr().out


def test_config_is_read_from_pyproject(project, capsys):
    (project / "pyproject.toml").write_text("[tool.promptlint]\ntoken_budget = 5\n")
    (project / "p.md").write_text("word " * 50)
    main([str(project), "--fail-on", "none"])
    assert "budget of 5" in capsys.readouterr().out


def test_missing_path_is_a_usage_error(tmp_path, capsys):
    assert main([str(tmp_path / "nope")]) == 2
    assert "no such file" in capsys.readouterr().err


def test_list_rules(capsys):
    assert main(["--list-rules"]) == 0
    out = capsys.readouterr().out
    assert out.count("PL00") == 7
