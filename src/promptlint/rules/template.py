"""PL001-PL003 — the placeholder rules."""

from __future__ import annotations

from collections.abc import Iterator

from promptlint.diagnostics import Diagnostic, Fix, Severity
from promptlint.placeholders import scan
from promptlint.rules.base import Rule, RuleContext, register
from promptlint.sources import PromptSource

_FIXABLE_KINDS = {"text"}


@register
class UnescapedBraces(Rule):
    code = "PL001"
    name = "unescaped-braces"
    summary = "Braces that .format() will choke on — usually a literal JSON example."
    severity = Severity.ERROR

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        if prompt.kind == "python-fstring":
            return  # an f-string is already balanced by the parser

        fields, errors = scan(prompt.text)

        for error in errors:
            if error.kind == "unmatched_open":
                yield self.report(
                    prompt,
                    error.start,
                    "unmatched '{' — .format() will raise ValueError on this template",
                    hint="Close the placeholder, or write '{{' if you meant a literal brace.",
                )
            else:
                yield self.report(
                    prompt,
                    error.start,
                    "unmatched '}' — .format() will raise ValueError on this template",
                    hint="Write '}}' if you meant a literal brace.",
                )

        for field in fields:
            if field.is_valid:
                continue
            snippet = prompt.text[field.start : field.end]
            preview = snippet if len(snippet) <= 40 else snippet[:37] + "..."
            fix = None
            if prompt.kind in _FIXABLE_KINDS:
                line, column = prompt.position(field.start)
                fix = Fix(
                    line=line,
                    column=column,
                    old=snippet,
                    new=snippet.replace("{", "{{").replace("}", "}}"),
                    description="escape the braces so they stay literal",
                )
            yield self.report(
                prompt,
                field.start,
                f"{preview!r} is not a valid placeholder — .format() will fail here",
                hint=(
                    "Literal braces (JSON examples, LaTeX, code blocks) must be doubled: "
                    "'{{' and '}}'."
                ),
                fix=fix,
            )


@register
class MissingVariable(Rule):
    code = "PL002"
    name = "missing-variable"
    summary = "The template needs a variable the call site never supplies."
    severity = Severity.ERROR

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        declared = _declared(prompt, ctx)
        if declared is None:
            return
        fields, _ = scan(prompt.text)
        seen: set[str] = set()
        for field in fields:
            if not field.is_valid or field.root in declared or field.root in seen:
                continue
            seen.add(field.root)
            yield self.report(
                prompt,
                field.start,
                f"template uses {{{field.root}}} but it is never supplied — KeyError at runtime",
                hint=f"Supplied here: {_render(declared)}.",
            )


@register
class UnusedVariable(Rule):
    code = "PL003"
    name = "unused-variable"
    summary = "A variable is supplied but the template never uses it."
    severity = Severity.WARNING

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        declared = _declared(prompt, ctx)
        if declared is None:
            return
        fields, _ = scan(prompt.text)
        used = {f.root for f in fields if f.is_valid}
        for name in sorted(declared - used):
            yield self.report(
                prompt,
                0,
                f"{name!r} is supplied to this prompt but never appears in it",
                hint="Either drop it at the call site, or you meant to reference it and forgot.",
            )


def _declared(prompt: PromptSource, ctx: RuleContext) -> frozenset[str] | None:
    if prompt.declared is not None:
        return prompt.declared
    if prompt.kind in {"text", "yaml"} and ctx.config.declared_variables:
        return frozenset(ctx.config.declared_variables)
    return None


def _render(names: frozenset[str]) -> str:
    return ", ".join(sorted(names)) if names else "nothing"
