from __future__ import annotations

from agent.decisions import AgentAction, AgentCompletion, AgentStep
from agent.loop import AgentContext


class OracleAgent:
    """Scripted agent that replays a predetermined sequence of actions.

    Used for testing the loop, interceptor, and evaluation pipeline
    without a model.
    """

    def __init__(self, script: list[AgentStep]) -> None:
        self._script = list(script)
        self._index = 0

    def step(self, context: AgentContext) -> AgentStep | None:
        if self._index >= len(self._script):
            return None
        action = self._script[self._index]
        self._index += 1
        return action
