"""Central scenario registry. Import all scenario modules, expose them by split."""
from __future__ import annotations

from scenarios.training.cleanup_scenarios import SCENARIOS as _cleanup
from scenarios.training.comms_scenarios import SCENARIOS as _comms
from scenarios.training.config_scenarios import SCENARIOS as _config
from scenarios.training.recovery_scenarios import SCENARIOS as _recovery
from scenarios.training.data_ops_scenarios import SCENARIOS as _data_ops
from scenarios.training.devops_scenarios import SCENARIOS as _devops
from scenarios.training.admin_scenarios import SCENARIOS as _admin
from scenarios.training.content_scenarios import SCENARIOS as _content
from scenarios.training.contrastive_scenarios import SCENARIOS as _contrastive
from scenarios.training.policy_diversity_scenarios import SCENARIOS as _policy_diverse
from scenarios.training.ask_boundary_scenarios import SCENARIOS as _ask_boundary
from scenarios.eval_structural.novel_tools import SCENARIOS as _novel
from scenarios.eval_structural.indirect_language import SCENARIOS as _indirect
from scenarios.eval_structural.multi_step import SCENARIOS as _multi
from scenarios.eval_indist.holdout import SCENARIOS as _indist
from scenarios.eval_structural_b.conditional_authority import SCENARIOS as _cond
from scenarios.eval_structural_b.cumulative_authority import SCENARIOS as _cumul
from scenarios.eval_structural_b.delegation_scope import SCENARIOS as _deleg
from scenarios.eval_structural_b.policy_composition import SCENARIOS as _comp
from scenarios.eval_structural_c.temporal_validity import SCENARIOS as _temp
from scenarios.eval_structural_c.action_lifecycle import SCENARIOS as _lifecycle
from scenarios.eval_structural_c.provenance_ownership import SCENARIOS as _prov
from scenarios.eval_structural_c.unknown_classification import SCENARIOS as _unk_class

ALL_SCENARIOS = (
    _cleanup + _comms + _config + _recovery
    + _data_ops + _devops + _admin + _content
    + _contrastive + _policy_diverse + _ask_boundary
    + _novel + _indirect + _indist + _multi
    + _cond + _cumul + _deleg + _comp
    + _temp + _lifecycle + _prov + _unk_class
)

TRAINING = [s for s in ALL_SCENARIOS if s.split == "training"]
EVAL_STRUCTURAL = [s for s in ALL_SCENARIOS if s.split == "eval_structural"]
EVAL_STRUCTURAL_B = [s for s in ALL_SCENARIOS if s.split == "eval_structural_b"]
EVAL_STRUCTURAL_C = [s for s in ALL_SCENARIOS if s.split == "eval_structural_c"]
EVAL_INDIST = [s for s in ALL_SCENARIOS if s.split == "eval_indist"]


def by_id(scenario_id: str):
    for s in ALL_SCENARIOS:
        if s.scenario_id == scenario_id:
            return s
    raise KeyError(f"Unknown scenario: {scenario_id}")


def by_tag(tag: str):
    return [s for s in ALL_SCENARIOS if tag in s.tags]


def by_difficulty(difficulty: str):
    return [s for s in ALL_SCENARIOS if s.difficulty == difficulty]
