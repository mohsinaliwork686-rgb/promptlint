"""PL006 — user input interpolated with nothing separating it from your instructions."""

from __future__ import annotations

import re
from collections.abc import Iterator

from promptlint.diagnostics import Diagnostic, Severity
from promptlint.placeholders import scan
from promptlint.rules.base import Rule, RuleContext, register
from promptlint.sources import PromptSource

#: Delimiters strong enough to count as a boundary.
_DELIMITERS = ("```", '"""', "'''", "<<<", ">>>", "===", "---", "###", "|||", '"', "'", "[", "]")
_OPEN_TAG_RE = re.compile(r"<([A-Za-z][\w:-]*)>[ \t]*$")
_SUFFIX_HINTS = ("_input", "_text", "_query", "_message", "_content", "_question", "_data")


@register
class UndelimitedUserInput(Rule):
    code = "PL006"
    name = "undelimited-user-input"
    summary = "Untrusted input is concatenated straight into the instructions."
    severity = Severity.WARNING

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        known = {name.lower() for name in ctx.config.user_input_variables}
        fields, _ = scan(prompt.text)
        for field in fields:
            root = field.root
            if not field.is_valid or not _looks_like_user_input(root, known):
                continue
            if _is_delimited(prompt.text, field.start, field.end):
                continue
            yield self.report(
                prompt,
                field.start,
                f"{{{root}}} holds untrusted input but is not delimited",
                hint=(
                    "Wrap it so the model can tell data from instructions, e.g. "
                    f"<untrusted_input>{{{root}}}</untrusted_input>, then instruct the model "
                    "to treat anything inside the tags as data, never as instructions."
                ),
            )


def _looks_like_user_input(root: str, known: set[str]) -> bool:
    lowered = root.lower()
    return lowered in known or lowered.endswith(_SUFFIX_HINTS)


def _is_delimited(text: str, start: int, end: int) -> bool:
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    if before.endswith(_DELIMITERS) and after.startswith(_DELIMITERS):
        return True
    match = _OPEN_TAG_RE.search(text[:start].rstrip("\n").rstrip())
    if match and re.match(r"\s*</" + re.escape(match.group(1)) + r">", text[end:]):
        return True
    return False
