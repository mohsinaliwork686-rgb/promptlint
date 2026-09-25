"""Scanner for ``str.format`` placeholders that keeps exact offsets."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

_ROOT_RE = re.compile(r"^[^.\[]*")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Field:
    """One ``{...}`` span found in a template."""

    raw: str          # everything between the braces
    start: int        # offset of the opening brace
    end: int          # offset just past the closing brace
    auto_index: int | None = None

    @property
    def spec(self) -> str:
        """The field name, with any ``!conversion`` and ``:format_spec`` stripped."""
        depth = 0
        for index, char in enumerate(self.raw):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif depth == 0 and char in ":!":
                return self.raw[:index]
        return self.raw

    @property
    def root(self) -> str:
        """``user.name`` -> ``user``; ``items[0]`` -> ``items``; ``{}`` -> its index."""
        name = _ROOT_RE.match(self.spec).group(0)
        if not name and self.auto_index is not None:
            return str(self.auto_index)
        return name

    @property
    def is_valid(self) -> bool:
        """Would ``.format()`` accept this as a placeholder at all?"""
        root = self.root
        return bool(root) and (root.isdigit() or bool(_IDENTIFIER_RE.match(root)))


@dataclass(frozen=True)
class BraceError:
    kind: str         # "unmatched_open" | "unmatched_close"
    start: int
    end: int


def scan(text: str) -> tuple[list[Field], list[BraceError]]:
    """Walk the template once, returning its placeholders and its brace errors."""
    fields: list[Field] = []
    errors: list[BraceError] = []
    index = 0
    length = len(text)
    auto_counter = 0

    while index < length:
        char = text[index]
        if char == "{":
            if index + 1 < length and text[index + 1] == "{":
                index += 2
                continue
            depth = 1
            cursor = index + 1
            while cursor < length and depth:
                if text[cursor] == "{":
                    depth += 1
                elif text[cursor] == "}":
                    depth -= 1
                cursor += 1
            if depth:
                errors.append(BraceError("unmatched_open", index, length))
                break
            raw = text[index + 1 : cursor - 1]
            auto = None
            if not _ROOT_RE.match(raw.split(":")[0].split("!")[0]).group(0):
                auto = auto_counter
                auto_counter += 1
            fields.append(Field(raw=raw, start=index, end=cursor, auto_index=auto))
            index = cursor
        elif char == "}":
            if index + 1 < length and text[index + 1] == "}":
                index += 2
                continue
            errors.append(BraceError("unmatched_close", index, index + 1))
            index += 1
        else:
            index += 1

    return fields, errors


def referenced_names(fields: Iterator[Field]) -> set[str]:
    return {f.root for f in fields if f.is_valid}
