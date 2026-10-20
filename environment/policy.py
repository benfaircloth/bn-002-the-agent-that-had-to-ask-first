from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Authority(Enum):
    ALLOWED = "allowed"
    APPROVAL_REQUIRED = "approval_required"
    PROHIBITED = "prohibited"


@dataclass(frozen=True)
class PolicyRule:
    """A single authority rule.

    The match function receives (tool_name, arguments, state) and returns
    True if this rule applies.  Rules are evaluated in order; the first
    match wins.
    """
    description: str
    authority: Authority
    match: Callable[..., bool]


class AuthorityPolicy:
    """Ordered collection of rules that maps (action, object, context) to
    an authority level.

    Rules are checked in order.  The first matching rule determines the
    authority.  If no rule matches, the default authority applies.
    """

    def __init__(
        self,
        rules: list[PolicyRule],
        default: Authority = Authority.PROHIBITED,
        natural_language: str = "",
    ) -> None:
        self.rules = list(rules)
        self.default = default
        self.natural_language = natural_language

    def check(self, tool_name: str, arguments: dict, state=None) -> Authority:
        for rule in self.rules:
            if rule.match(tool_name, arguments, state):
                return rule.authority
        return self.default

    def explain(self, tool_name: str, arguments: dict, state=None) -> tuple[Authority, str]:
        """Return authority level and the description of the matching rule."""
        for rule in self.rules:
            if rule.match(tool_name, arguments, state):
                return rule.authority, rule.description
        return self.default, "no matching rule; default applies"
