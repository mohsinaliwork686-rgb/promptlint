"""PL004 — credentials baked into a prompt."""

from __future__ import annotations

import re
from collections.abc import Iterator

from promptlint.diagnostics import Diagnostic, Severity
from promptlint.rules.base import Rule, RuleContext, register
from promptlint.sources import PromptSource

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI API key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36}")),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{50,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("JSON web token", re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-.=]{20,}")),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret[_-]?key|secret|access[_-]?token|auth[_-]?token"
            r"|password|passwd|private[_-]?key)\b\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9_\-]{16,})"
        ),
    ),
)

#: Values that look like credentials but are obviously stand-ins.
_PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:x{6,}|\.{3,}|your[_-].*|my[_-].*|.*[_-]?here$|.*example.*|.*placeholder.*"
    r"|.*dummy.*|.*redacted.*|.*changeme.*|.*fake.*|test[_-].*|sk-(?:test|xxx).*|"
    r"(?:abc|123|000|aaa)[A-Za-z0-9_\-]*)$"
)


@register
class HardcodedSecret(Rule):
    code = "PL004"
    name = "hardcoded-secret"
    summary = "A credential is embedded in the prompt text."
    severity = Severity.ERROR

    def check(self, prompt: PromptSource, ctx: RuleContext) -> Iterator[Diagnostic]:
        seen: set[int] = set()
        for label, pattern in _PATTERNS:
            for match in pattern.finditer(prompt.text):
                if "value" in pattern.groupindex:
                    value, start = match.group("value"), match.start("value")
                else:
                    value, start = match.group(0), match.start()
                if _PLACEHOLDER_RE.match(value) or start in seen:
                    continue
                seen.add(start)
                yield self.report(
                    prompt,
                    start,
                    f"{label} found in prompt text ({_redact(value)})",
                    hint=(
                        "Prompts get logged, cached and sent to third parties. "
                        "Read the credential from the environment and pass it as a header, "
                        "never inside the prompt."
                    ),
                )


def _redact(value: str) -> str:
    head = value[:4]
    return f"{head}...{len(value)} chars"
