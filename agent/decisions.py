from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from environment.interceptor import Decision


@dataclass
class AgentAction:
    """A single action the agent wants to take."""
    tool: str
    arguments: dict[str, Any]
    decision: Decision
    reasoning: str = ""


@dataclass
class AgentCompletion:
    """The agent declares the task finished."""
    summary: str
    pending_approvals: list[str] | None = None


AgentStep = AgentAction | AgentCompletion
