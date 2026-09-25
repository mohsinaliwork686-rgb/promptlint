"""Rule registry — importing this module registers every built-in rule."""

from __future__ import annotations

from promptlint.rules import template  # noqa: F401
from promptlint.rules.base import REGISTRY, Rule, RuleContext, all_rules, register

__all__ = ["REGISTRY", "Rule", "RuleContext", "all_rules", "register"]
