"""Extraction and position mapping."""

from __future__ import annotations

from promptlint.sources import discover, extract


def test_front_matter_declares_variables(tmp_path):
    path = tmp_path / "p.md"
    path.write_text("---\nname: greet\nvariables: [name, tone]\n---\nHello {name}\n")
    (prompt,) = extract(path)
    assert prompt.name == "greet"
    assert prompt.declared == frozenset({"name", "tone"})
    assert prompt.text.startswith("Hello")
    assert prompt.line_offset == 5


def test_front_matter_block_list(tmp_path):
    path = tmp_path / "p.md"
    path.write_text("---\nvariables:\n  - alpha\n  - beta\n---\nHi {alpha}\n")
    (prompt,) = extract(path)
    assert prompt.declared == frozenset({"alpha", "beta"})


def test_position_maps_to_file_line_and_column(tmp_path):
    path = tmp_path / "p.md"
    path.write_text("---\nvariables: [q]\n---\nline one\nAnswer {q} now\n")
    (prompt,) = extract(path)
    offset = prompt.text.index("{q}")
    assert prompt.position(offset) == (5, 8)


def test_python_format_call_supplies_declared_names(tmp_path):
    path = tmp_path / "a.py"
    path.write_text(
        'SYSTEM_PROMPT = """Hello {name}\nand {other}"""\n'
        "x = SYSTEM_PROMPT.format(name=1, other=2)\n"
    )
    (prompt,) = extract(path)
    assert prompt.name == "SYSTEM_PROMPT"
    assert prompt.declared == frozenset({"name", "other"})
    assert prompt.position(prompt.text.index("{other}")) == (2, 5)


def test_python_star_kwargs_leaves_declared_unknown(tmp_path):
    path = tmp_path / "a.py"
    path.write_text('PROMPT = "Hi {name}"\nx = PROMPT.format(**values)\n')
    (prompt,) = extract(path)
    assert prompt.declared is None


def test_python_fstring_is_captured_without_brace_checks(tmp_path):
    path = tmp_path / "a.py"
    path.write_text('user_input = "x"\nPROMPT_TEXT = f"Answer: {user_input}"\n')
    (prompt,) = extract(path)
    assert prompt.kind == "python-fstring"
    assert "{user_input}" in prompt.text


def test_python_ignores_non_prompt_strings(tmp_path):
    path = tmp_path / "a.py"
    path.write_text('GREETING = "hello"\nVALUE = "world"\n')
    assert extract(path) == []


def test_yaml_block_scalar_keeps_line_numbers(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text("agents:\n  one:\n    system: |\n      First line\n      {document}\n")
    (prompt,) = extract(path)
    assert prompt.name == "system"
    assert prompt.text == "First line\n{document}"
    assert prompt.position(prompt.text.index("{document}")) == (5, 7)


def test_yaml_inline_string(tmp_path):
    path = tmp_path / "p.yaml"
    path.write_text('prompt: "Summarize for {audience}"\n')
    (prompt,) = extract(path)
    assert prompt.text == "Summarize for {audience}"


def test_discover_skips_vendor_directories(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "p.md").write_text("x")
    (tmp_path / "keep.md").write_text("x")
    (tmp_path / "ignore.png").write_text("x")
    assert discover([tmp_path]) == [tmp_path / "keep.md"]
