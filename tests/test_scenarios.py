"""Tests for scenario registry and scenario consistency."""
from scenarios.registry import (
    ALL_SCENARIOS, TRAINING, EVAL_STRUCTURAL, EVAL_STRUCTURAL_B,
    EVAL_STRUCTURAL_C, EVAL_INDIST,
    by_id, by_tag, by_difficulty,
)


def test_all_scenarios_have_unique_ids():
    ids = [s.scenario_id for s in ALL_SCENARIOS]
    assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"


def test_split_counts():
    assert len(TRAINING) == 142
    assert len(EVAL_STRUCTURAL) == 41
    assert len(EVAL_STRUCTURAL_B) == 28
    assert len(EVAL_STRUCTURAL_C) == 21
    assert len(EVAL_INDIST) == 6


def test_splits_partition_all():
    total = (
        len(TRAINING) + len(EVAL_STRUCTURAL) + len(EVAL_STRUCTURAL_B)
        + len(EVAL_STRUCTURAL_C) + len(EVAL_INDIST)
    )
    assert total == len(ALL_SCENARIOS)


def test_every_scenario_has_expected_actions():
    for s in ALL_SCENARIOS:
        assert len(s.expected_actions) > 0, f"{s.scenario_id} has no expected actions"


def test_every_scenario_has_policy():
    for s in ALL_SCENARIOS:
        assert s.policy_natural_language, f"{s.scenario_id} has no policy description"


def test_by_id():
    s = by_id("train-cleanup-001")
    assert s.scenario_id == "train-cleanup-001"


def test_by_id_missing():
    try:
        by_id("nonexistent")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass


def test_by_tag():
    tagged = by_tag("cleanup")
    assert all("cleanup" in s.tags for s in tagged)
    assert len(tagged) >= 3


def test_by_difficulty():
    easy = by_difficulty("easy")
    assert all(s.difficulty == "easy" for s in easy)
    assert len(easy) >= 2
