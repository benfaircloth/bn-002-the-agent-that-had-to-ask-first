"""Few-shot example selection for condition 3.

Picks training scenarios that demonstrate all four decision types (ACT, ASK,
REFUSE, CONTINUE) with clear, representative policies. The examples are
converted to message sequences that get prepended to the conversation.
"""
from __future__ import annotations

import json

from environment.interceptor import Decision
from scenarios.scenario import Scenario


EXEMPLAR_IDS = [
    "train-cleanup-001",
    "train-cleanup-002",
    "train-recovery-001",
]


def select_exemplars(training_scenarios: list[Scenario]) -> list[Scenario]:
    by_id = {s.scenario_id: s for s in training_scenarios}
    found = [by_id[sid] for sid in EXEMPLAR_IDS if sid in by_id]
    if len(found) < 3:
        remaining = [s for s in training_scenarios if s.scenario_id not in EXEMPLAR_IDS]
        found.extend(remaining[:3 - len(found)])
    return found


def exemplars_to_messages(exemplars: list[Scenario]) -> list[dict]:
    """Convert exemplar scenarios into assistant/user message pairs.

    Each exemplar becomes a demonstration: the user states the task,
    the assistant shows the correct trajectory as a sequence of JSON
    actions with observations interleaved.
    """
    messages = []

    for scenario in exemplars:
        messages.append({
            "role": "user",
            "content": (
                f"Example task: {scenario.task}\n\n"
                f"Available files:\n"
                + "\n".join(f"  - {f['path']}" for f in scenario.files)
            ),
        })

        action_sequence = []
        for ea in scenario.expected_actions:
            action_obj = {
                "tool": ea.tool,
                "arguments": ea.arguments,
                "decision": ea.decision.value,
                "reasoning": ea.note or f"{ea.decision.value} per policy",
            }
            action_sequence.append(json.dumps(action_obj))

            if ea.decision == Decision.ACT:
                action_sequence.append(json.dumps({
                    "status": "success", "tool": ea.tool,
                }))
            elif ea.decision == Decision.ASK:
                action_sequence.append(json.dumps({
                    "status": "pending_approval", "tool": ea.tool,
                }))
            elif ea.decision == Decision.REFUSE:
                action_sequence.append(json.dumps({
                    "status": "refused", "tool": ea.tool,
                }))

        action_sequence.append(json.dumps({
            "status": "complete",
            "summary": "Task finished. See pending approvals for escalated items.",
            "pending_approvals": [
                ea.tool + " " + str(ea.arguments)
                for ea in scenario.expected_actions
                if ea.decision == Decision.ASK
            ],
        }))

        messages.append({
            "role": "assistant",
            "content": "\n".join(action_sequence),
        })

    return messages
