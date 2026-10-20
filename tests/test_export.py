"""Tests for SFT and GRPO export pipelines."""
import json
import tempfile
from pathlib import Path

from environment.interceptor import Decision
from export.reasoning import generate_reasoning
from export.sft import export_sft, export_sft_turns, scenario_to_conversation
from export.grpo import (
    compute_reward,
    export_grpo_prompts,
    export_reference_trajectories,
    VIOLATION_CEILING,
)
from scenarios.registry import TRAINING, by_id


def test_reasoning_generation():
    s = by_id("train-cleanup-001")
    for action in s.expected_actions:
        reasoning = generate_reasoning(action, s.policy_natural_language, [])
        assert len(reasoning) > 0
        if action.decision == Decision.ACT:
            assert "executing" in reasoning.lower() or "within my authority" in reasoning.lower()
        elif action.decision == Decision.ASK:
            assert "approval" in reasoning.lower() or "escalat" in reasoning.lower()
        elif action.decision == Decision.REFUSE:
            assert "prohibited" in reasoning.lower() or "refus" in reasoning.lower()


def test_reasoning_with_prior_blocks():
    s = by_id("train-recovery-001")
    prior_blocks = ["delete_file(path=/production/batch-c.csv)"]
    last_act = [a for a in s.expected_actions if a.decision == Decision.ACT][-1]
    reasoning = generate_reasoning(last_act, s.policy_natural_language, prior_blocks)
    assert "continuing" in reasoning.lower() or "remaining" in reasoning.lower()


def test_scenario_to_conversation_with_reasoning():
    s = by_id("train-cleanup-001")
    conv = scenario_to_conversation(s, include_reasoning=True)

    messages = conv["messages"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    first_action = json.loads(assistant_msgs[0]["content"])
    assert "reasoning" in first_action
    assert len(first_action["reasoning"]) > 0


def test_scenario_to_conversation_without_reasoning():
    s = by_id("train-cleanup-001")
    conv = scenario_to_conversation(s, include_reasoning=False)

    messages = conv["messages"]
    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    first_action = json.loads(assistant_msgs[0]["content"])
    assert "reasoning" not in first_action


def test_scenario_to_conversation_structure():
    s = by_id("train-cleanup-001")
    conv = scenario_to_conversation(s)

    assert "messages" in conv
    assert "metadata" in conv
    assert conv["metadata"]["scenario_id"] == "train-cleanup-001"

    messages = conv["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "authority policy" in messages[0]["content"].lower()
    assert s.task in messages[1]["content"]

    assistant_msgs = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_msgs) >= len(s.expected_actions)

    first_action = json.loads(assistant_msgs[0]["content"])
    assert "tool" in first_action
    assert "decision" in first_action


def test_export_sft():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "sft.jsonl"
        n = export_sft(TRAINING[:5], path)

        assert n == 5
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 5

        for line in lines:
            data = json.loads(line)
            assert "messages" in data
            assert data["messages"][0]["role"] == "system"


def test_export_sft_no_reasoning():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "sft.jsonl"
        n = export_sft(TRAINING[:3], path, include_reasoning=False)

        assert n == 3
        lines = path.read_text().strip().split("\n")
        for line in lines:
            data = json.loads(line)
            for msg in data["messages"]:
                if msg["role"] == "assistant":
                    try:
                        parsed = json.loads(msg["content"])
                        if "tool" in parsed:
                            assert "reasoning" not in parsed
                    except json.JSONDecodeError:
                        pass


def test_export_sft_turns():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "sft-turns.jsonl"
        scenarios = TRAINING[:3]
        n = export_sft_turns(scenarios, path)

        total_actions = sum(len(s.expected_actions) for s in scenarios)
        assert n == total_actions

        lines = path.read_text().strip().split("\n")
        assert len(lines) == total_actions

        first = json.loads(lines[0])
        assert first["metadata"]["step"] == 1
        last_msg = first["messages"][-1]
        assert last_msg["role"] == "assistant"


def test_export_grpo_prompts():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "grpo.jsonl"
        n = export_grpo_prompts(TRAINING[:5], path)

        assert n == 5
        lines = path.read_text().strip().split("\n")

        for line in lines:
            data = json.loads(line)
            assert "messages" in data
            assert "ground_truth" in data
            assert len(data["ground_truth"]) > 0
            for gt in data["ground_truth"]:
                assert gt["decision"] in ("act", "ask", "refuse")


def test_export_reference_trajectories():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "reference.jsonl"
        n = export_reference_trajectories(TRAINING[:5], path)

        assert n == 5
        lines = path.read_text().strip().split("\n")

        for line in lines:
            data = json.loads(line)
            assert "messages" in data
            assert "reward" in data
            assert isinstance(data["reward"], (int, float))


def test_compute_reward_perfect():
    s = by_id("train-cleanup-002")
    gold = [
        {"tool": ea.tool, "arguments": ea.arguments, "decision": ea.decision.value}
        for ea in s.expected_actions
    ]
    reward = compute_reward(gold, s.expected_actions)
    assert reward > 0.8


def test_compute_reward_violation_cap():
    """Unauthorized actions cap the reward at VIOLATION_CEILING."""
    s = by_id("train-cleanup-002")
    bad = [
        {"tool": ea.tool, "arguments": ea.arguments, "decision": "act"}
        for ea in s.expected_actions
    ]
    reward = compute_reward(bad, s.expected_actions)
    assert reward <= VIOLATION_CEILING


def test_compute_reward_all_wrong_less_than_perfect():
    s = by_id("train-cleanup-002")
    bad = [
        {"tool": ea.tool, "arguments": ea.arguments, "decision": "act"}
        for ea in s.expected_actions
    ]
    reward = compute_reward(bad, s.expected_actions)
    good = [
        {"tool": ea.tool, "arguments": ea.arguments, "decision": ea.decision.value}
        for ea in s.expected_actions
    ]
    good_reward = compute_reward(good, s.expected_actions)
    assert reward < good_reward


def test_compute_reward_empty():
    s = by_id("train-cleanup-001")
    reward = compute_reward([], s.expected_actions)
    assert reward == -1.0


def test_full_training_export():
    """Smoke test: export all training scenarios in all formats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)

        n_sft = export_sft(TRAINING, base / "sft.jsonl")
        n_turns = export_sft_turns(TRAINING, base / "turns.jsonl")
        n_grpo = export_grpo_prompts(TRAINING, base / "grpo.jsonl")
        n_ref = export_reference_trajectories(TRAINING, base / "reference.jsonl")

        assert n_sft == len(TRAINING)
        assert n_turns == sum(len(s.expected_actions) for s in TRAINING)
        assert n_grpo == len(TRAINING)
        assert n_ref == len(TRAINING)
