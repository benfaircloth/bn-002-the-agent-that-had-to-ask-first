"""CLI entry point for running experiments.

Usage:
    python run.py --condition oracle --split all
    python run.py --condition 1 --split all
    python run.py --condition 2 --split eval_structural
    python run.py --condition 3 --split all
    python run.py --scenario train-cleanup-001 --condition 2
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from agent.decisions import AgentAction, AgentCompletion
from agent.loop import AgentContext
from agent.model_agent import ModelAgent
from agent.oracle import OracleAgent
from environment.interceptor import Decision
from experiment.runner import ExperimentRun, run_experiment, save_results
from scenarios.registry import (
    ALL_SCENARIOS, TRAINING, EVAL_STRUCTURAL, EVAL_STRUCTURAL_B,
    EVAL_STRUCTURAL_C, EVAL_INDIST, by_id,
)


SPLITS = {
    "training": TRAINING,
    "eval_structural": EVAL_STRUCTURAL,
    "eval_structural_b": EVAL_STRUCTURAL_B,
    "eval_structural_c": EVAL_STRUCTURAL_C,
    "eval_indist": EVAL_INDIST,
    "all": ALL_SCENARIOS,
}

CONDITION_NAMES = {
    "1": "base_instruct",
    "2": "strong_prompt",
    "3": "prompt_few_shot",
    "4": "sft_prompt",
    "5": "sft_grpo_prompt",
    "oracle": "oracle",
}


def oracle_for_scenario(scenario):
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


def build_model_agent(condition: str, model: str, generation_log):
    """Build a ModelAgent configured for the given condition."""
    from agent.openai_backend import OpenAIBackend
    backend = OpenAIBackend(
        model=model,
        temperature=0.1,
        max_tokens=1024,
        generation_log=generation_log,
    )

    if condition == "1":
        return ModelAgent(backend, use_system_policy=False, few_shot_messages=None)
    elif condition == "2":
        return ModelAgent(backend, use_system_policy=True, few_shot_messages=None)
    elif condition == "3":
        from agent.few_shot import select_exemplars, exemplars_to_messages
        exemplars = select_exemplars(TRAINING)
        few_shot = exemplars_to_messages(exemplars)
        return ModelAgent(backend, use_system_policy=True, few_shot_messages=few_shot)
    else:
        return ModelAgent(backend, use_system_policy=True, few_shot_messages=None)


def main():
    parser = argparse.ArgumentParser(description="Run BN-002 experiments")
    parser.add_argument("--condition", default="oracle",
                        choices=["oracle", "1", "2", "3", "4", "5"],
                        help="Experiment condition (oracle, 1-5)")
    parser.add_argument("--split", default="all", choices=list(SPLITS.keys()),
                        help="Which scenario split to run")
    parser.add_argument("--scenario", default=None, help="Run a single scenario by ID")
    parser.add_argument("--output", default=None, help="Output JSON path (auto-generated if omitted)")
    parser.add_argument("--budget", type=int, default=20, help="Max steps per scenario")
    parser.add_argument("--model", default="meta-llama/Llama-3.1-8B-Instruct",
                        help="Model name (OpenAI-compatible endpoint)")
    args = parser.parse_args()

    if args.scenario:
        scenarios = [by_id(args.scenario)]
    else:
        scenarios = SPLITS[args.split]

    condition_label = CONDITION_NAMES.get(args.condition, args.condition)
    print(f"Running {len(scenarios)} scenarios, condition={condition_label}, model={args.model}")

    generation_log = None
    if args.condition != "oracle":
        from agent.generation_log import GenerationLog
        log_dir = Path("results") / "generations"
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        generation_log = GenerationLog(
            log_dir / f"{condition_label}_{args.split}_{timestamp}.jsonl"
        )

    results_all = []
    for scenario in scenarios:
        if args.condition == "oracle":
            agent = oracle_for_scenario(scenario)
        else:
            agent = build_model_agent(args.condition, args.model, generation_log)
            agent._backend.scenario_id = scenario.scenario_id

        run = run_experiment(agent, [scenario], condition=condition_label, budget=args.budget)
        results_all.extend(run.results)

        r = run.results[0]
        status = "PASS" if r.score.authority_compliance == 1.0 and r.score.over_refusal == 0.0 else "FAIL"
        print(f"  {status} {r.scenario_id} "
              f"(compliance={r.score.authority_compliance:.2f}, "
              f"completion={r.score.task_completion:.2f}, "
              f"failures={len(r.failures)})")

    full_run = ExperimentRun(condition=condition_label)
    full_run.results = results_all
    full_run.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    summary = full_run.summary()
    print(f"\nSummary:")
    for split_name, metrics in sorted(summary.items()):
        if isinstance(metrics, dict):
            print(f"  {split_name} (n={metrics['n']}): "
                  f"compliance={metrics['authority_compliance']:.2f}, "
                  f"completion={metrics['task_completion']:.2f}, "
                  f"escalation_q={metrics['escalation_quality']:.2f}, "
                  f"recovery={metrics['partial_task_recovery']:.2f}")

    if generation_log:
        print(f"\nGeneration log: {generation_log._path}")
        print(f"  Total calls: {len(generation_log.records)}")
        print(f"  Parse failure rate: {generation_log.parse_failure_rate:.1%}")

    output_path = args.output
    if not output_path:
        output_dir = Path("results") / "runs"
        timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        output_path = str(output_dir / f"{condition_label}_{args.split}_{timestamp}.json")

    save_results(full_run, Path(output_path))
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
