"""PL005 — prompts that blow the token budget."""

from __future__ import annotations

from collections.abc import Iterator

from promptlint.diagnostics import Diagnostic, Severity
from promptlint.rules.base import Rule, RuleContext, register
from promptlint.sources import PromptSource
from promptlint.tokens import estimate_tokens


@register
class TokenBudget(Rule):
    code = "PL005"
    name = "token-budget"
    summary = "The template is larger than the configured token budget."
    severity = Severity.WARNING

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        budget = ctx.config.token_budget
        if budget <= 0:
            return
        count, exact = estimate_tokens(prompt.text, ctx.config.tokenizer)
        if count <= budget:
            return
        qualifier = "" if exact else "~"
        hint = (
            "This is the static template alone — every variable you interpolate adds more. "
            "Raise token_budget in [tool.promptlint] if this is intentional."
        )
        if not exact:
            hint += " Install promptlint[tokens] for exact counts."
        yield self.report(
            prompt,
            0,
            f"prompt is {qualifier}{count} tokens, over the budget of {budget}",
            hint=hint,
        )
