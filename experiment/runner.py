"""Experiment runner: execute an agent across scenarios and collect results."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent.loop import Agent, Trajectory, run_task
from environment.interceptor import Decision
from environment.policy import Authority, AuthorityPolicy, PolicyRule
from environment.state import EnvironmentState, FileEntry
from evaluation.metrics import TrajectoryScore, score_trajectory
from evaluation.taxonomy import Failure, classify_failures
from scenarios.scenario import Scenario


@dataclass
class ScenarioResult:
    scenario_id: str
    split: str
    tags: list[str]
    difficulty: str
    score: TrajectoryScore
    failures: list[Failure]
    trajectory_steps: int
    completed: bool
    hit_budget: bool
    elapsed_seconds: float


@dataclass
class ExperimentRun:
    condition: str
    timestamp: str = ""
    results: list[ScenarioResult] = field(default_factory=list)

    def summary(self) -> dict:
        by_split: dict[str, list[ScenarioResult]] = {}
        for r in self.results:
            by_split.setdefault(r.split, []).append(r)

        out = {"condition": self.condition, "timestamp": self.timestamp}
        for split, results in sorted(by_split.items()):
            scores = [r.score for r in results]
            out[split] = {
                "n": len(results),
                "task_completion": _mean([s.task_completion for s in scores]),
                "authority_compliance": _mean([s.authority_compliance for s in scores]),
                "over_refusal": _mean([s.over_refusal for s in scores]),
                "escalation_quality": _mean([s.escalation_quality for s in scores]),
                "partial_task_recovery": _mean([s.partial_task_recovery for s in scores]),
                "failure_count": sum(len(r.failures) for r in results),
            }
        return out


def build_policy_from_scenario(scenario: Scenario) -> AuthorityPolicy:
    """Build a functional policy from a scenario's expected actions.

    Structural holdout scenarios use policy_natural_language instead of
    policy_rules. For oracle-based testing, we derive the policy from
    the expected actions so the interceptor can score correctly.
    """
    rules = []
    for ea in scenario.expected_actions:
        if ea.decision == Decision.ACT:
            authority = Authority.ALLOWED
        elif ea.decision == Decision.ASK:
            authority = Authority.APPROVAL_REQUIRED
        elif ea.decision == Decision.REFUSE:
            authority = Authority.PROHIBITED
        else:
            authority = Authority.ALLOWED

        tool = ea.tool
        args = ea.arguments.copy()
        rules.append(PolicyRule(
            description=ea.note or f"{tool} on {args}",
            authority=authority,
            match=_exact_match(tool, args),
        ))

    rules.append(PolicyRule(
        description="reading any file is allowed",
        authority=Authority.ALLOWED,
        match=lambda t, a, s=None: t == "read_file",
    ))

    return AuthorityPolicy(
        rules=rules,
        default=Authority.ALLOWED,
        natural_language=scenario.policy_natural_language,
    )


def run_experiment(
    agent: Agent,
    scenarios: list[Scenario],
    condition: str = "base",
    budget: int = 20,
) -> ExperimentRun:
    run = ExperimentRun(
        condition=condition,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )

    for scenario in scenarios:
        state = EnvironmentState([
            FileEntry(f["path"], f["content"], f.get("category", "general"))
            for f in scenario.files
        ])

        policy = build_policy_from_scenario(scenario)

        t0 = time.monotonic()
        trajectory = run_task(
            agent=agent,
            task=scenario.task,
            state=state,
            policy=policy,
            task_id=scenario.scenario_id,
            budget=budget,
        )
        elapsed = time.monotonic() - t0

        score = score_trajectory(trajectory, scenario.expected_actions)
        failures = classify_failures(trajectory)

        run.results.append(ScenarioResult(
            scenario_id=scenario.scenario_id,
            split=scenario.split,
            tags=scenario.tags,
            difficulty=scenario.difficulty,
            score=score,
            failures=failures,
            trajectory_steps=len(trajectory.steps),
            completed=trajectory.completed,
            hit_budget=trajectory.hit_budget,
            elapsed_seconds=round(elapsed, 3),
        ))

    return run


def save_results(run: ExperimentRun, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "condition": run.condition,
        "timestamp": run.timestamp,
        "summary": run.summary(),
        "results": [
            {
                "scenario_id": r.scenario_id,
                "split": r.split,
                "tags": r.tags,
                "difficulty": r.difficulty,
                "score": asdict(r.score),
                "failures": [
                    {
                        "type": f.failure_type.value,
                        "step": f.step,
                        "tool": f.tool,
                        "detail": f.detail,
                    }
                    for f in r.failures
                ],
                "trajectory_steps": r.trajectory_steps,
                "completed": r.completed,
                "hit_budget": r.hit_budget,
                "elapsed_seconds": r.elapsed_seconds,
            }
            for r in run.results
        ],
    }

    path.write_text(json.dumps(data, indent=2) + "\n")


def _exact_match(tool: str, args: dict):
    def match(t, a, s=None):
        if t != tool:
            return False
        return all(a.get(k) == v for k, v in args.items() if v is not None)
    return match


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
