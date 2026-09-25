"""Rule protocol and registry."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from promptlint.config import Config
from promptlint.diagnostics import Diagnostic, Severity
from promptlint.sources import PromptSource


@dataclass
class RuleContext:
    config: Config


class Rule:
    """Base class. Subclasses set the metadata and implement :meth:`check`."""

    code: str = ""
    name: str = ""
    summary: str = ""
    severity: Severity = Severity.WARNING

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        raise NotImplementedError

    # convenience ---------------------------------------------------------

    def report(
        self,
        prompt: PromptSource,
        offset: int,
        message: str,
        *,
        hint: str | None = None,
        severity: Severity | None = None,
        fix=None,
    ) -> Diagnostic:
        line, column = prompt.position(offset)
        return Diagnostic(
            code=self.code,
            message=message,
            path=str(prompt.path),
            line=line,
            column=column,
            severity=severity or self.severity,
            hint=hint,
            prompt_name=prompt.name,
            fix=fix,
        )


REGISTRY: list[Rule] = []


def register(cls: type[Rule]) -> type[Rule]:
    REGISTRY.append(cls())
    return cls


def all_rules() -> list[Rule]:
    return sorted(REGISTRY, key=lambda r: r.code)
