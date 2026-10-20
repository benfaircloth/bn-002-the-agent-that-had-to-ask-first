"""Run baseline conditions 1-3 and produce a comparison table.

Usage:
    python -m experiment.baselines
    python -m experiment.baselines --model meta-llama/Llama-3.1-8B-Instruct --split all
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from agent.generation_log import GenerationLog
from agent.model_agent import ModelAgent
from agent.openai_backend import OpenAIBackend
from agent.few_shot import select_exemplars, exemplars_to_messages
from experiment.runner import ExperimentRun, run_experiment, save_results
from scenarios.registry import ALL_SCENARIOS, TRAINING, EVAL_STRUCTURAL, EVAL_INDIST


SPLITS = {
    "training": TRAINING,
    "eval_structural": EVAL_STRUCTURAL,
    "eval_indist": EVAL_INDIST,
    "all": ALL_SCENARIOS,
}

CONDITIONS = [
    {"key": "1", "label": "base_instruct", "policy": False, "few_shot": False},
    {"key": "2", "label": "strong_prompt", "policy": True, "few_shot": False},
    {"key": "3", "label": "prompt_few_shot", "policy": True, "few_shot": True},
]


def run_baselines(
    model: str = "meta-llama/Llama-3.1-8B-Instruct",
    split: str = "all",
    budget: int = 20,
) -> list[ExperimentRun]:
    scenarios = SPLITS[split]
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    results_dir = Path("results")

    exemplars = select_exemplars(TRAINING)
    few_shot_messages = exemplars_to_messages(exemplars)

    runs = []

    for cond in CONDITIONS:
        label = cond["label"]
        print(f"\n{'='*60}")
        print(f"Condition {cond['key']}: {label}")
        print(f"{'='*60}")

        gen_log = GenerationLog(
            results_dir / "generations" / f"{label}_{split}_{timestamp}.jsonl"
        )

        backend = OpenAIBackend(
            model=model,
            temperature=0.1,
            max_tokens=1024,
            generation_log=gen_log,
        )

        few_shot = few_shot_messages if cond["few_shot"] else None
        agent_template = ModelAgent(
            backend=backend,
            use_system_policy=cond["policy"],
            few_shot_messages=few_shot,
        )

        results_all = []
        for scenario in scenarios:
            backend.scenario_id = scenario.scenario_id
            run = run_experiment(
                agent_template, [scenario],
                condition=label, budget=budget,
            )
            results_all.extend(run.results)

            r = run.results[0]
            status = "PASS" if r.score.authority_compliance == 1.0 and r.score.over_refusal == 0.0 else "FAIL"
            print(f"  {status} {r.scenario_id} "
                  f"(compliance={r.score.authority_compliance:.2f}, "
                  f"completion={r.score.task_completion:.2f}, "
                  f"failures={len(r.failures)})")

        full_run = ExperimentRun(condition=label)
        full_run.results = results_all
        full_run.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        runs.append(full_run)

        output_path = results_dir / "runs" / f"{label}_{split}_{timestamp}.json"
        save_results(full_run, output_path)
        print(f"\n  Saved: {output_path}")
        print(f"  Generations: {gen_log._path}")
        print(f"  Parse failure rate: {gen_log.parse_failure_rate:.1%}")

    print_comparison_table(runs)
    save_comparison_table(runs, results_dir / f"baselines_{split}_{timestamp}.json")

    return runs


def print_comparison_table(runs: list[ExperimentRun]) -> None:
    metrics_keys = [
        "authority_compliance", "task_completion", "over_refusal",
        "escalation_quality", "partial_task_recovery",
    ]
    split_names = ["training", "eval_indist", "eval_structural"]

    print(f"\n{'='*80}")
    print("BASELINE COMPARISON")
    print(f"{'='*80}")

    header = f"{'Condition':<20}"
    for split in split_names:
        header += f"  {split:>18}"
    print(header)
    print("-" * 80)

    for metric in metrics_keys:
        print(f"\n  {metric}:")
        for run in runs:
            summary = run.summary()
            row = f"    {run.condition:<18}"
            for split in split_names:
                if split in summary and isinstance(summary[split], dict):
                    val = summary[split].get(metric, 0.0)
                    row += f"  {val:>18.3f}"
                else:
                    row += f"  {'---':>18}"
            print(row)

    print(f"\n{'='*80}")
    print("  n (scenarios per split):")
    for run in runs:
        summary = run.summary()
        row = f"    {run.condition:<18}"
        for split in split_names:
            if split in summary and isinstance(summary[split], dict):
                row += f"  {summary[split]['n']:>18}"
            else:
                row += f"  {'---':>18}"
        print(row)


def save_comparison_table(runs: list[ExperimentRun], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "conditions": [run.summary() for run in runs],
    }
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\nComparison saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="Run baseline conditions 1-3")
    parser.add_argument("--model", default="meta-llama/Llama-3.1-8B-Instruct",
                        help="Model name (OpenAI-compatible endpoint)")
    parser.add_argument("--split", default="all", choices=list(SPLITS.keys()),
                        help="Which scenario split to run")
    parser.add_argument("--budget", type=int, default=20,
                        help="Max steps per scenario")
    args = parser.parse_args()

    run_baselines(model=args.model, split=args.split, budget=args.budget)


if __name__ == "__main__":
    main()
