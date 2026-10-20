from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from agent.decisions import AgentAction, AgentCompletion, AgentStep
from environment.interceptor import ActionRecord, Decision, Interceptor
from environment.policy import AuthorityPolicy
from environment.state import EnvironmentState
from environment.tools import ToolRegistry


@dataclass
class StepRecord:
    """What happened on one turn of the loop."""
    step_number: int
    agent_step: AgentStep
    action_record: ActionRecord | None


@dataclass
class Trajectory:
    """Full record of one task execution."""
    task_id: str
    task: str
    steps: list[StepRecord] = field(default_factory=list)
    completed: bool = False
    completion_summary: str = ""
    pending_approvals: list[str] = field(default_factory=list)
    hit_budget: bool = False


@dataclass
class AgentContext:
    """Everything the agent sees at each decision point."""
    task: str
    tool_manifest: list[dict]
    policy_description: str
    available_files: list[str]
    step_history: list[StepRecord]


class Agent(Protocol):
    def step(self, context: AgentContext) -> AgentStep | None: ...


def run_task(
    agent: Agent,
    task: str,
    state: EnvironmentState,
    policy: AuthorityPolicy,
    registry: ToolRegistry | None = None,
    task_id: str = "",
    budget: int = 20,
) -> Trajectory:
    if registry is None:
        registry = ToolRegistry()

    interceptor = Interceptor(registry, policy, state, task_id=task_id)
    trajectory = Trajectory(task_id=task_id, task=task)

    for turn in range(1, budget + 1):
        context = AgentContext(
            task=task,
            tool_manifest=registry.manifest(),
            policy_description=policy.natural_language,
            available_files=state.list_files(),
            step_history=list(trajectory.steps),
        )

        agent_step = agent.step(context)

        if agent_step is None:
            trajectory.completed = True
            break

        if isinstance(agent_step, AgentCompletion):
            trajectory.steps.append(StepRecord(turn, agent_step, None))
            trajectory.completed = True
            trajectory.completion_summary = agent_step.summary
            trajectory.pending_approvals = agent_step.pending_approvals or []
            break

        record = interceptor.attempt(
            agent_step.tool, agent_step.arguments, agent_step.decision
        )
        trajectory.steps.append(StepRecord(turn, agent_step, record))

    else:
        trajectory.hit_budget = True

    return trajectory
