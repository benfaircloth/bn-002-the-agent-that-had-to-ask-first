# BN-002: The Agent That Had to Ask First

Companion code for [Build Note 002](https://benfaircloth.com/buildnotes/bn-002-the-agent-that-had-to-ask-first).

## Question

Can supervised fine-tuning teach a tool-using agent to reliably distinguish authorized, approval-required, and prohibited actions? And does that boundary transfer to structurally novel scenarios the model has never seen?

## Setup

Llama 3.1 8B Instruct on MI300X. Full fine-tuning, not LoRA.

The agent uses a four-way decision model: **ACT** (execute), **ASK** (escalate for approval), **REFUSE** (decline), **CONTINUE** (proceed with remaining authorized work after a block). An authority policy engine evaluates each action against ordered rules. An interceptor sits between the agent and the tool layer, recording the agent's *attempted* decision separately from whether the action was actually executed. This separation is the core measurement: an unauthorized attempt is an authority failure even if the environment blocks it.

## Conditions

| # | Condition | Training | System prompt | Few-shot |
|---|-----------|----------|---------------|----------|
| 1 | `base_instruct` | None | None | No |
| 2 | `strong_prompt` | None | Full authority policy | No |
| 3 | `prompt_few_shot` | None | Full authority policy | 3 exemplars |
| 4 | `sft_prompt` (SFT1) | 73 scenarios, 3 epochs | Full authority policy | No |
| 4b | `sft_prompt` (SFT2) | 142 scenarios, 3 epochs | Full authority policy | No |
| 5 | `sft_grpo_prompt` | SFT + GRPO | Full authority policy | No |

Condition 5 was not completed. See [Failure Analysis](#failure-analysis).

## Evaluation

238 scenarios across five splits:

| Split | Count | Purpose |
|-------|-------|---------|
| Training | 142 | SFT data source. Also evaluated to detect overfitting. |
| In-distribution holdout | 6 | Same tools and policy concepts, unseen tasks. |
| Structural A | 41 | Novel tools, indirect language, multi-step dependencies. |
| Structural B | 28 | Conditional authority, cumulative authority, delegation scope, policy composition. |
| Structural C | 21 | Temporal validity, action lifecycle, provenance/ownership, unknown classification. |

Six metrics per trajectory:

- **Authority compliance**: fraction of actions where the agent's decision matched the required authority level.
- **Task completion**: fraction of authorized actions the agent actually executed.
- **Over-refusal**: fraction of authorized actions the agent unnecessarily escalated or refused.
- **Escalation quality**: fraction of approval-required actions correctly escalated (not acted on or refused).
- **Partial task recovery**: whether the agent continued authorized work after encountering a blocked action.
- **Decision efficiency**: ratio of expected actions to total actions taken.

## Results

The central finding is a structural transfer gap.

**SFT1** (73 training examples): 0.71 authority compliance on training scenarios. 0.21 on structural holdouts. The model learned the decision vocabulary but defaulted to ACT on unfamiliar authority structures.

**SFT2** (142 training examples): 0.68 on training. 0.13 on structural holdouts. More training data made the gap worse, not better. The model fit the training distribution more tightly without learning the underlying boundary principle.

Both conditions show the same pattern: high compliance on scenarios that resemble the training data, near-zero compliance on scenarios that require the same *kind* of reasoning applied to novel tools, policies, or interaction patterns.

## Structure

```
agent/
  decisions.py         ACT/ASK/REFUSE/CONTINUE dataclasses
  loop.py              Agent protocol, run_task(), trajectory recording
  model_agent.py       LLM-backed agent with Backend protocol
  openai_backend.py    OpenAI-compatible backend (Together, vLLM, etc.)
  oracle.py            Scripted agent for testing the pipeline
  few_shot.py          Exemplar selection and message formatting
  generation_log.py    Per-call logging for debugging and replay

environment/
  policy.py            AuthorityPolicy: ordered rules, first match wins
  interceptor.py       Records attempted decisions separately from execution
  state.py             Simulated workspace with full mutation history
  tools.py             Tool registry and dispatch

scenarios/
  scenario.py          Scenario and ExpectedAction dataclasses
  library.py           Reusable policy factories and environment builders
  registry.py          Central scenario index, split accessors
  training/            142 training scenarios (11 modules)
  eval_structural/     41 structural holdout A scenarios
  eval_structural_b/   28 structural holdout B scenarios
  eval_structural_c/   21 structural holdout C scenarios
  eval_indist/         6 in-distribution holdout scenarios

evaluation/
  metrics.py           Six-metric trajectory scorer
  taxonomy.py          Failure classifier (unauthorized, premature escalation, etc.)

export/
  sft.py               Scenario-to-conversation exporter for SFT
  grpo.py              GRPO prompt/reward exporter with confusion-matrix reward
  reasoning.py         Policy-grounded reasoning generator for training data

experiment/
  runner.py            Run agent across scenarios, collect results
  baselines.py         Conditions 1-3 comparison runner
  rescore.py           Re-score saved generation logs with updated scorer
```

## Running

Install dependencies:

```bash
pip install -e .
```

Copy `.env.example` to `.env` and set your API key and base URL:

```bash
cp .env.example .env
```

Run the oracle baseline (no API calls, validates the pipeline):

```bash
python run.py --condition oracle --split all
```

Run a model condition against a single scenario:

```bash
python run.py --condition 2 --scenario train-cleanup-001 --model meta-llama/Llama-3.1-8B-Instruct
```

Run all baselines:

```bash
python -m experiment.baselines --model meta-llama/Llama-3.1-8B-Instruct
```

Export SFT training data:

```bash
python -c "
from scenarios.registry import TRAINING
from export.sft import export_sft
from pathlib import Path
export_sft(TRAINING, Path('data/sft-training.jsonl'))
"
```

Run tests:

```bash
pytest
```

## Failure Analysis

Structural holdouts test seven categories of generalization:

1. **Novel tools**: tools the model never saw during training.
2. **Indirect language**: policies that describe authority without using the words "allowed" or "prohibited."
3. **Multi-step dependencies**: actions whose authority depends on the outcome of prior actions.
4. **Conditional authority**: authority that changes based on argument values or environment state.
5. **Cumulative authority**: authority that shifts after repeated actions of the same type.
6. **Delegation scope**: authority inherited from or limited by another agent's permissions.
7. **Unknown classification**: actions that don't match any policy rule, where the correct response is to escalate rather than guess.

The model consistently defaulted to ACT on unfamiliar authority structures. It learned to produce well-formatted decisions with plausible reasoning, but the reasoning did not drive the decision. When the structural pattern was unfamiliar, the model reverted to its base behavior: execute the action.

GRPO (condition 5) was designed to address this by rewarding correct authority decisions with a confusion-matrix reward function. The reward function and export pipeline are included in `export/grpo.py`. The GRPO condition was not completed because the structural transfer gap in SFT indicated a more fundamental problem than reward shaping alone could address.

## Related

- [Build Note 002: The Agent That Had to Ask First](https://benfaircloth.com/buildnotes/bn-002-the-agent-that-had-to-ask-first)
- [TN-002: From Measurements to Decisions](https://benfaircloth.com/teaching/tn-002-from-measurements-to-decisions)
- [FN-002: The Benchmark Ends at Deployment](https://benfaircloth.com/fieldnotes/002-the-benchmark-ends-at-deployment)

## License

MIT
