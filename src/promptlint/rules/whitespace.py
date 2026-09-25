"""PL007 — trailing whitespace, which quietly degrades completions."""

from __future__ import annotations

import re
from collections.abc import Iterator

from promptlint.diagnostics import Diagnostic, Fix, Severity
from promptlint.rules.base import Rule, RuleContext, register
from promptlint.sources import PromptSource

_TRAILING_RE = re.compile(r"[ \t]+$", re.MULTILINE)
_FIXABLE_KINDS = {"text", "yaml"}


@register
class TrailingWhitespace(Rule):
    code = "PL007"
    name = "trailing-whitespace"
    summary = "Trailing whitespace before the model starts generating."
    severity = Severity.WARNING

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        text = prompt.text
        for match in _TRAILING_RE.finditer(text):
            at_end = match.end() == len(text.rstrip("\n")) and not text[match.end():].strip()
            line, column = prompt.position(match.start())
            fix = None
            if prompt.kind in _FIXABLE_KINDS:
                fix = Fix(
                    line=line,
                    column=column,
                    old=match.group(0),
                    new="",
                    description="strip trailing whitespace",
                )
            if at_end:
                message = "prompt ends with trailing whitespace"
                hint = (
                    "Tokenizers attach the trailing space to the next token, which makes the "
                    "model less likely to produce the continuation you want. Strip it."
                )
            else:
                message = "trailing whitespace"
                hint = "Invisible in review, and it changes the tokenization of the line."
            yield self.report(prompt, match.start(), message, hint=hint, fix=fix)
