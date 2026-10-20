"""Re-score saved generation logs with the current scorer.

Replays cached model responses through the agent loop without making
new API calls. Use after fixing scoring bugs to get corrected results
from existing runs.

Usage:
    python -m experiment.rescore results/generations/base_instruct_all_20261015_153452.jsonl
    python -m experiment.rescore --all-baselines
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

from agent.model_agent import ModelAgent
from experiment.runner import ExperimentRun, run_experiment, save_results
from scenarios.registry import ALL_SCENARIOS, TRAINING, EVAL_STRUCTURAL, EVAL_INDIST


class ReplayBackend:
    """Backend that returns cached responses from a generation log."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._index = 0
        self._scenario_id = ""

    @property
    def scenario_id(self) -> str:
        return self._scenario_id

    @scenario_id.setter
    def scenario_id(self, value: str) -> None:
        self._scenario_id = value

    def complete(self, messages: list[dict]) -> str:
        if self._index >= len(self._responses):
            return '{"status": "complete", "summary": "budget exhausted"}'
        resp = self._responses[self._index]
        self._index += 1
        return resp

    def reset(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._index = 0


def load_generation_log(path: Path) -> dict[str, list[str]]:
    """Load a generation log, grouped by scenario_id in order."""
    by_scenario: dict[str, list[str]] = defaultdict(list)
    with open(path) as f:
        for line in f:
            rec = json.loads(line)
            by_scenario[rec["scenario_id"]].append(rec["raw_response"])
    return dict(by_scenario)


def rescore_log(
    log_path: Path,
    condition_label: str,
    use_system_policy: bool,
    few_shot_messages: list[dict] | None = None,
) -> ExperimentRun:
    responses_by_scenario = load_generation_log(log_path)
    scenarios_by_id = {s.scenario_id: s for s in ALL_SCENARIOS}

    backend = ReplayBackend([])
    agent = ModelAgent(
        backend=backend,
        use_system_policy=use_system_policy,
        few_shot_messages=few_shot_messages,
    )

    results_all = []
    for scenario_id, responses in responses_by_scenario.items():
        if scenario_id not in scenarios_by_id:
            continue
        scenario = scenarios_by_id[scenario_id]
        backend.reset(responses)
        backend.scenario_id = scenario_id

        run = run_experiment(agent, [scenario], condition=condition_label, budget=20)
        results_all.extend(run.results)

        r = run.results[0]
        status = "PASS" if r.score.authority_compliance == 1.0 and r.score.over_refusal == 0.0 else "FAIL"
        print(f"  {status} {r.scenario_id} "
              f"(compliance={r.score.authority_compliance:.2f}, "
              f"completion={r.score.task_completion:.2f}, "
              f"over_refusal={r.score.over_refusal:.2f}, "
              f"failures={len(r.failures)})")

    full_run = ExperimentRun(condition=condition_label)
    full_run.results = results_all
    full_run.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return full_run


def print_comparison(runs: list[ExperimentRun]) -> None:
    metrics_keys = [
        "authority_compliance", "task_completion", "over_refusal",
        "escalation_quality", "partial_task_recovery",
    ]
    split_names = ["training", "eval_indist", "eval_structural"]

    print(f"\n{'='*80}")
    print("RESCORED BASELINE COMPARISON")
    print(f"{'='*80}")

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


def main():
    parser = argparse.ArgumentParser(description="Re-score generation logs")
    parser.add_argument("log_path", nargs="?", help="Path to generation JSONL")
    parser.add_argument("--all-baselines", action="store_true",
                        help="Re-score all baseline generation logs")
    args = parser.parse_args()

    gen_dir = Path("results/generations")
    timestamp = "20261015_153452"

    if args.all_baselines or not args.log_path:
        from agent.few_shot import select_exemplars, exemplars_to_messages
        exemplars = select_exemplars(TRAINING)
        few_shot = exemplars_to_messages(exemplars)

        configs = [
            (gen_dir / f"base_instruct_all_{timestamp}.jsonl", "base_instruct", False, None),
            (gen_dir / f"strong_prompt_all_{timestamp}.jsonl", "strong_prompt", True, None),
            (gen_dir / f"prompt_few_shot_all_{timestamp}.jsonl", "prompt_few_shot", True, few_shot),
        ]

        runs = []
        for log_path, label, policy, fs in configs:
            if not log_path.exists():
                print(f"Skipping {label}: {log_path} not found")
                continue
            print(f"\n{'='*60}")
            print(f"Rescoring: {label}")
            print(f"{'='*60}")
            run = rescore_log(log_path, label, policy, fs)
            runs.append(run)

            out_path = Path("results/runs") / f"{label}_all_rescored.json"
            save_results(run, out_path)
            print(f"  Saved: {out_path}")

        print_comparison(runs)

        comparison_path = Path("results") / f"baselines_all_rescored.json"
        comparison_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "conditions": [run.summary() for run in runs],
        }
        comparison_path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"\nComparison saved to {comparison_path}")
    else:
        run = rescore_log(Path(args.log_path), "rescored", True)
        out_path = Path("results/runs/rescored.json")
        save_results(run, out_path)
        print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
