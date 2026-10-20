from __future__ import annotations

from dataclasses import dataclass, field

from environment.interceptor import Decision


@dataclass
class ExpectedAction:
    """One step of the expected trajectory."""
    tool: str
    arguments: dict
    decision: Decision
    note: str = ""


@dataclass
class Scenario:
    """A complete test case: initial state, policy, task, and expected behavior."""
    scenario_id: str
    task: str
    files: list[dict]
    policy_rules: list[dict]
    policy_natural_language: str
    expected_actions: list[ExpectedAction]
    split: str = "training"
    tags: list[str] = field(default_factory=list)
    difficulty: str = "medium"
