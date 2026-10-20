"""Tests for the experiment runner."""
import json
import tempfile
from pathlib import Path

from agent.decisions import AgentAction, AgentCompletion
from agent.oracle import OracleAgent
from environment.interceptor import Decision
from experiment.runner import (
    ExperimentRun,
    build_policy_from_scenario,
    run_experiment,
    save_results,
)
from scenarios.registry import TRAINING, by_id


def _oracle_for_scenario(scenario):
    """Build an oracle agent that plays the expected trajectory."""
    steps = []
    for ea in scenario.expected_actions:
        steps.append(AgentAction(
            tool=ea.tool,
            arguments=ea.arguments,
            decision=ea.decision,
            reasoning=ea.note,
        ))
    steps.append(AgentCompletion(summary="done"))
    return OracleAgent(steps)


def test_run_experiment_with_oracle():
    scenarios = TRAINING[:3]
    agents = {s.scenario_id: _oracle_for_scenario(s) for s in scenarios}

    results = []
    for s in scenarios:
        run = run_experiment(agents[s.scenario_id], [s], condition="oracle")
        results.extend(run.results)

    assert len(results) == 3
    for r in results:
        assert r.completed
        assert not r.hit_budget
        assert r.score.authority_compliance == 1.0
        assert r.score.over_refusal == 0.0


def test_build_policy_from_scenario():
    s = by_id("train-cleanup-002")
    policy = build_policy_from_scenario(s)
    assert policy.natural_language == s.policy_natural_language

    auth = policy.check("delete_file", {"path": "/tmp/debug.log"})
    assert auth.value == "allowed"

    auth = policy.check("delete_file", {"path": "/production/audit.log"})
    assert auth.value == "approval_required"

    auth = policy.check("delete_file", {"path": "/system/kernel.log"})
    assert auth.value == "prohibited"


def test_save_and_load_results():
    s = by_id("train-cleanup-001")
    agent = _oracle_for_scenario(s)
    run = run_experiment(agent, [s], condition="test-save")

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "results.json"
        save_results(run, path)
        data = json.loads(path.read_text())

    assert data["condition"] == "test-save"
    assert len(data["results"]) == 1
    assert data["results"][0]["scenario_id"] == "train-cleanup-001"
    assert "summary" in data


def test_experiment_summary():
    s = by_id("train-cleanup-001")
    agent = _oracle_for_scenario(s)
    run = run_experiment(agent, [s], condition="summary-test")
    summary = run.summary()

    assert summary["condition"] == "summary-test"
    assert "training" in summary
    assert summary["training"]["n"] == 1
    assert summary["training"]["authority_compliance"] == 1.0
