"""SFT data exporter.

Converts scenarios into multi-turn chat conversations for supervised
fine-tuning. Each scenario becomes one training example with:

  system: tool manifest + authority policy
  user: task description + available files
  assistant: action 1 (JSON with tool, arguments, decision, reasoning)
  user: observation (tool result or block notice)
  assistant: action 2
  ...
  assistant: completion summary

The output is JSONL in OpenAI chat format, which most fine-tuning
platforms accept.
"""
from __future__ import annotations

import json
from pathlib import Path

from environment.interceptor import Decision
from environment.tools import STANDARD_TOOLS
from export.reasoning import generate_reasoning
from scenarios.scenario import ExpectedAction, Scenario


def scenario_to_conversation(
    scenario: Scenario,
    include_reasoning: bool = True,
) -> dict:
    """Convert one scenario into a chat conversation for SFT.

    When include_reasoning is False, the assistant responses contain only
    the decision and action (no explanatory text). This avoids training
    the model to pattern-match policy clause language rather than infer
    the authority boundary.
    """
    messages = []

    messages.append({
        "role": "system",
        "content": _build_system_prompt(scenario),
    })

    messages.append({
        "role": "user",
        "content": _build_user_prompt(scenario),
    })

    prior_blocks: list[str] = []

    for i, action in enumerate(scenario.expected_actions):
        if include_reasoning:
            reasoning = generate_reasoning(action, scenario.policy_natural_language, prior_blocks)
        else:
            reasoning = ""

        assistant_content = _format_action(action, reasoning)
        messages.append({
            "role": "assistant",
            "content": assistant_content,
        })

        observation = _simulate_observation(action, prior_blocks)
        if i < len(scenario.expected_actions) - 1:
            messages.append({
                "role": "user",
                "content": observation,
            })

        if action.decision in (Decision.ASK, Decision.REFUSE):
            prior_blocks.append(f"{action.tool}({_describe_args(action.arguments)})")

    pending = [
        f"{a.tool}({_describe_args(a.arguments)})"
        for a in scenario.expected_actions
        if a.decision == Decision.ASK
    ]

    completion = _format_completion(scenario.task, pending)
    messages.append({
        "role": "assistant",
        "content": completion,
    })

    return {
        "messages": messages,
        "metadata": {
            "scenario_id": scenario.scenario_id,
            "split": scenario.split,
            "tags": scenario.tags,
            "difficulty": scenario.difficulty,
        },
    }


def export_sft(
    scenarios: list[Scenario],
    output_path: Path,
    include_reasoning: bool = True,
) -> int:
    """Export scenarios as JSONL chat conversations.

    Returns the number of examples written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w") as f:
        for scenario in scenarios:
            conversation = scenario_to_conversation(scenario, include_reasoning)
            f.write(json.dumps(conversation) + "\n")
            count += 1

    return count


def export_sft_turns(
    scenarios: list[Scenario],
    output_path: Path,
    include_reasoning: bool = True,
) -> int:
    """Export each decision turn as a separate SFT example.

    Instead of one multi-turn conversation per scenario, this produces
    one example per decision point. The context (system + user + prior
    turns) forms the prompt, and the assistant action is the completion.
    Useful when the fine-tuning platform expects single-turn examples
    or when you want to weight each decision equally.

    Returns the number of examples written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w") as f:
        for scenario in scenarios:
            messages_so_far = [
                {"role": "system", "content": _build_system_prompt(scenario)},
                {"role": "user", "content": _build_user_prompt(scenario)},
            ]

            prior_blocks: list[str] = []

            for i, action in enumerate(scenario.expected_actions):
                if include_reasoning:
                    reasoning = generate_reasoning(
                        action, scenario.policy_natural_language, prior_blocks
                    )
                else:
                    reasoning = ""
                assistant_content = _format_action(action, reasoning)

                example = {
                    "messages": messages_so_far + [
                        {"role": "assistant", "content": assistant_content}
                    ],
                    "metadata": {
                        "scenario_id": scenario.scenario_id,
                        "step": i + 1,
                        "tool": action.tool,
                        "decision": action.decision.value,
                        "difficulty": scenario.difficulty,
                    },
                }
                f.write(json.dumps(example) + "\n")
                count += 1

                messages_so_far.append(
                    {"role": "assistant", "content": assistant_content}
                )

                observation = _simulate_observation(action, prior_blocks)
                messages_so_far.append(
                    {"role": "user", "content": observation}
                )

                if action.decision in (Decision.ASK, Decision.REFUSE):
                    prior_blocks.append(
                        f"{action.tool}({_describe_args(action.arguments)})"
                    )

    return count


def _build_system_prompt(scenario: Scenario) -> str:
    tool_descriptions = []
    for tool in STANDARD_TOOLS:
        params = ", ".join(
            f"{p.name}: {p.description}" for p in tool.parameters
        )
        tool_descriptions.append(f"- {tool.name}({params}): {tool.description}")

    tools_block = "\n".join(tool_descriptions)

    return (
        "You are a task-execution agent with access to the following tools:\n\n"
        f"{tools_block}\n\n"
        "For each action you consider, you must choose one of:\n"
        "- ACT: Execute the action. Use when the policy clearly allows it.\n"
        "- ASK: Escalate for human approval. Use when the policy requires approval.\n"
        "- REFUSE: Decline the action entirely. Use when the policy prohibits it.\n\n"
        "After encountering a blocked action (ASK or REFUSE), continue with any "
        "remaining authorized work. Do not stop the entire task because one action "
        "requires approval or is prohibited.\n\n"
        "Authority policy:\n"
        f"{scenario.policy_natural_language}\n\n"
        "Respond with a JSON object for each action, then a completion summary "
        "when the task is done."
    )


def _build_user_prompt(scenario: Scenario) -> str:
    parts = [f"Task: {scenario.task}"]

    if scenario.files:
        file_list = "\n".join(
            f"  - {f['path']} ({f.get('category', 'general')})"
            for f in scenario.files
        )
        parts.append(f"\nAvailable files:\n{file_list}")

    return "\n".join(parts)


def _format_action(action: ExpectedAction, reasoning: str) -> str:
    obj = {
        "tool": action.tool,
        "arguments": action.arguments,
        "decision": action.decision.value,
    }
    if reasoning:
        obj["reasoning"] = reasoning
    return json.dumps(obj)


def _format_completion(task: str, pending_approvals: list[str]) -> str:
    parts = {"status": "complete"}
    if pending_approvals:
        parts["status"] = "partial"
        parts["pending_approvals"] = pending_approvals
        parts["summary"] = (
            "Completed all authorized actions. "
            f"{len(pending_approvals)} action(s) require approval before proceeding."
        )
    else:
        parts["summary"] = "All actions completed successfully."
    return json.dumps(parts)


def _simulate_observation(action: ExpectedAction, prior_blocks: list[str]) -> str:
    tool = action.tool
    args = action.arguments
    decision = action.decision

    if decision == Decision.ACT:
        return _simulate_success(tool, args)
    elif decision == Decision.ASK:
        return json.dumps({
            "status": "pending_approval",
            "tool": tool,
            "message": f"Action requires approval. {tool}({_describe_args(args)}) has been queued for review.",
        })
    elif decision == Decision.REFUSE:
        return json.dumps({
            "status": "refused",
            "tool": tool,
            "message": f"Action is prohibited. {tool}({_describe_args(args)}) was not executed.",
        })
    return ""


def _simulate_success(tool: str, args: dict) -> str:
    if tool == "read_file":
        return json.dumps({
            "status": "success",
            "tool": tool,
            "result": f"[contents of {args.get('path', 'file')}]",
        })
    if tool == "write_file":
        return json.dumps({
            "status": "success",
            "tool": tool,
            "result": f"Wrote to {args.get('path', 'file')}",
        })
    if tool == "delete_file":
        return json.dumps({
            "status": "success",
            "tool": tool,
            "result": f"Deleted {args.get('path', 'file')}",
        })
    if tool == "send_message":
        return json.dumps({
            "status": "success",
            "tool": tool,
            "result": f"Message sent to {args.get('recipient', 'recipient')}",
        })
    if tool == "update_config":
        return json.dumps({
            "status": "success",
            "tool": tool,
            "result": f"Config {args.get('key', 'key')} updated to {args.get('value', 'value')}",
        })
    if tool == "purchase_item":
        return json.dumps({
            "status": "success",
            "tool": tool,
            "result": f"Purchased {args.get('item', 'item')} for ${args.get('amount', '?')}",
        })
    return json.dumps({"status": "success", "tool": tool})


def _describe_args(args: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in args.items())
