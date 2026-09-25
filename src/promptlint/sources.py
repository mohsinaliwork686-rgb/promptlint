"""Find prompt templates inside files, keeping enough position data to report on them."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".jinja", ".j2", ".prompt", ".tmpl"}
YAML_SUFFIXES = {".yaml", ".yml"}
PYTHON_SUFFIXES = {".py"}
LINTABLE_SUFFIXES = TEXT_SUFFIXES | YAML_SUFFIXES | PYTHON_SUFFIXES

SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "build", "dist", ".tox", "site-packages",
}

#: Names that suggest a string is meant to be sent to a model.
PROMPT_NAME_RE = re.compile(
    r"(?i)(prompt|template|instruction|system_?m(sg|essage)|user_?m(sg|essage)|persona)"
)
PROMPT_KEY_NAMES = {"system", "user", "assistant", "content", "instructions"}


@dataclass
class PromptSource:
    """A single prompt template plus where it came from."""

    path: Path
    text: str
    name: str | None = None
    #: 1-based file line holding the first line of ``text``.
    line_offset: int = 1
    #: 0-based column on that first line where ``text`` begins.
    col_offset: int = 0
    #: Indentation stripped from continuation lines (YAML block scalars).
    body_indent: int = 0
    #: Variables the call site supplies. ``None`` means "we could not tell".
    declared: frozenset[str] | None = None
    #: ``False`` when newlines in ``text`` do not correspond to newlines in the file.
    maps_lines: bool = True
    #: One of ``text``, ``yaml``, ``python-str``, ``python-fstring``.
    kind: str = "text"
    meta: dict[str, object] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.name or self.path.name

    def position(self, offset: int) -> tuple[int, int]:
        """Map a character offset inside ``text`` to a 1-based (line, column) in the file."""
        offset = max(0, min(offset, len(self.text)))
        if not self.maps_lines:
            return (self.line_offset, self.col_offset + 1)
        prefix = self.text[:offset]
        rel_line = prefix.count("\n")
        if rel_line == 0:
            return (self.line_offset, self.col_offset + offset + 1)
        last_nl = prefix.rfind("\n")
        return (self.line_offset + rel_line, self.body_indent + offset - last_nl)


# --------------------------------------------------------------------------- discovery


def discover(paths: list[Path]) -> list[Path]:
    """Expand the given paths into a sorted list of lintable files."""
    found: set[Path] = set()
    for raw in paths:
        if raw.is_file():
            found.add(raw)
        elif raw.is_dir():
            for child in raw.rglob("*"):
                if not child.is_file() or child.suffix.lower() not in LINTABLE_SUFFIXES:
                    continue
                if any(part in SKIP_DIRS for part in child.parts):
                    continue
                found.add(child)
    return sorted(found)


def extract(path: Path) -> list[PromptSource]:
    """Pull every prompt template out of one file."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    suffix = path.suffix.lower()
    if suffix in PYTHON_SUFFIXES:
        return _from_python(path, raw)
    if suffix in YAML_SUFFIXES:
        return _from_yaml(path, raw)
    if suffix in TEXT_SUFFIXES:
        return _from_text(path, raw)
    return []


# --------------------------------------------------------------------------- text files

_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)


def _from_text(path: Path, raw: str) -> list[PromptSource]:
    name = None
    declared: frozenset[str] | None = None
    line_offset = 1
    body = raw

    match = _FRONT_MATTER_RE.match(raw)
    if match:
        meta = _parse_front_matter(match.group(1))
        name = meta.get("name")
        if "variables" in meta:
            declared = frozenset(meta["variables"])
        body = raw[match.end():]
        line_offset = raw[: match.end()].count("\n") + 1

    if not body.strip():
        return []
    return [
        PromptSource(
            path=path,
            text=body,
            name=name,
            line_offset=line_offset,
            declared=declared,
            kind="text",
        )
    ]


def _parse_front_matter(block: str) -> dict:
    """Parse the tiny subset of YAML we support in front matter, with no dependencies."""
    meta: dict = {}
    pending_list: str | None = None
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if pending_list and line.lstrip().startswith("- "):
            meta[pending_list].append(line.lstrip()[2:].strip().strip("\"'"))
            continue
        pending_list = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
            meta[key] = [v for v in items if v]
        elif value:
            meta[key] = value.strip("\"'")
        else:
            meta[key] = []
            pending_list = key
    return meta


# --------------------------------------------------------------------------- yaml files

_YAML_KEY_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<key>[A-Za-z_][\w.\-]*)[ \t]*:[ \t]*(?P<value>.*)$")
_BLOCK_SCALAR_RE = re.compile(r"^[|>][+-]?\d*$")


def _is_prompt_key(key: str) -> bool:
    return key.lower() in PROMPT_KEY_NAMES or bool(PROMPT_NAME_RE.search(key))


def _from_yaml(path: Path, raw: str) -> list[PromptSource]:
    """Scan YAML line by line so we keep exact line numbers (and need no yaml parser)."""
    lines = raw.splitlines()
    sources: list[PromptSource] = []
    index = 0
    while index < len(lines):
        match = _YAML_KEY_RE.match(lines[index])
        if not match or not _is_prompt_key(match.group("key")):
            index += 1
            continue

        key = match.group("key")
        value = match.group("value").strip()
        key_indent = len(match.group("indent").expandtabs(4))

        if _BLOCK_SCALAR_RE.match(value):
            body_lines: list[str] = []
            cursor = index + 1
            block_indent: int | None = None
            while cursor < len(lines):
                line = lines[cursor]
                if not line.strip():
                    body_lines.append("")
                    cursor += 1
                    continue
                indent = len(line) - len(line.lstrip())
                if indent <= key_indent:
                    break
                if block_indent is None:
                    block_indent = indent
                body_lines.append(line[block_indent:])
                cursor += 1
            body = "\n".join(body_lines).strip("\n")
            if body.strip():
                sources.append(
                    PromptSource(
                        path=path,
                        text=body,
                        name=key,
                        line_offset=index + 2,
                        col_offset=block_indent or 0,
                        body_indent=block_indent or 0,
                        kind="yaml",
                    )
                )
            index = cursor
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            body = value[1:-1]
            if body.strip():
                sources.append(
                    PromptSource(
                        path=path,
                        text=body,
                        name=key,
                        line_offset=index + 1,
                        col_offset=lines[index].index(value) + 1,
                        maps_lines=False,
                        kind="yaml",
                    )
                )
        index += 1
    return sources


# --------------------------------------------------------------------------- python files


def _from_python(path: Path, raw: str) -> list[PromptSource]:
    try:
        tree = ast.parse(raw, filename=str(path))
    except SyntaxError:
        return []

    collector = _PythonCollector(path)
    collector.visit(tree)
    return collector.results()


class _PythonCollector(ast.NodeVisitor):
    """Collect prompt-shaped string constants and enrich them from ``.format()`` call sites."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._by_node: dict[int, PromptSource] = {}
        self._by_name: dict[str, ast.Constant] = {}
        self._order: list[PromptSource] = []

    # -- collection -------------------------------------------------------

    def visit_Assign(self, node: ast.Assign) -> None:
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        prompt_names = [n for n in names if PROMPT_NAME_RE.search(n)]
        if names and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for name in names:
                self._by_name[name] = node.value
            if prompt_names:
                self._record_constant(node.value, prompt_names[0])
        elif prompt_names and isinstance(node.value, ast.JoinedStr):
            self._record_fstring(node.value, prompt_names[0])
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            self._handle_format(node)
        self.generic_visit(node)

    # -- helpers ----------------------------------------------------------

    def _record_constant(self, node: ast.Constant, name: str | None) -> PromptSource:
        existing = self._by_node.get(id(node))
        if existing is not None:
            return existing
        source = PromptSource(
            path=self.path,
            text=node.value,
            name=name,
            line_offset=node.lineno,
            col_offset=node.col_offset,
            maps_lines=node.end_lineno != node.lineno,
            kind="python-str",
        )
        self._by_node[id(node)] = source
        self._order.append(source)
        return source

    def _record_fstring(self, node: ast.JoinedStr, name: str | None) -> None:
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                try:
                    parts.append("{" + ast.unparse(value.value) + "}")
                except Exception:  # pragma: no cover - unparse is total in practice
                    parts.append("{...}")
        text = "".join(parts)
        if not text.strip():
            return
        self._order.append(
            PromptSource(
                path=self.path,
                text=text,
                name=name,
                line_offset=node.lineno,
                col_offset=node.col_offset,
                maps_lines=False,
                kind="python-fstring",
            )
        )

    def _handle_format(self, node: ast.Call) -> None:
        target = node.func.value  # type: ignore[union-attr]
        constant: ast.Constant | None = None
        name: str | None = None

        if isinstance(target, ast.Constant) and isinstance(target.value, str):
            constant = target
        elif isinstance(target, ast.Name) and target.id in self._by_name:
            constant = self._by_name[target.id]
            name = target.id

        if constant is None:
            return

        source = self._record_constant(constant, name or "format-template")
        if source.declared is not None:
            return  # first call site wins; a second would only add noise

        if any(kw.arg is None for kw in node.keywords) or any(
            isinstance(a, ast.Starred) for a in node.args
        ):
            return  # **kwargs — we cannot know what is supplied

        supplied = {kw.arg for kw in node.keywords if kw.arg}
        supplied |= {str(i) for i in range(len(node.args))}
        source.declared = frozenset(supplied)

    def results(self) -> list[PromptSource]:
        return [s for s in self._order if s.text.strip()]
