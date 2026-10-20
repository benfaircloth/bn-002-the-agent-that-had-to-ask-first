"""Generate reasoning text for each expected action.

The reasoning explains WHY the agent chose ACT/ASK/REFUSE for a given
action, grounded in the scenario's policy language. This is the critical
training signal for SFT: the model learns the mapping from policy
description to behavioral decision.
"""
from __future__ import annotations

from environment.interceptor import Decision
from scenarios.scenario import ExpectedAction


def generate_reasoning(
    action: ExpectedAction,
    policy_text: str,
    prior_blocks: list[str],
) -> str:
    """Produce a reasoning string for one expected action.

    Args:
        action: The expected action with tool, arguments, and decision.
        policy_text: The scenario's natural language policy.
        prior_blocks: Tools/descriptions of actions that were previously
            blocked in this trajectory (for recovery context).
    """
    tool = action.tool
    args = action.arguments
    decision = action.decision

    target = _describe_target(tool, args)

    if decision == Decision.ACT:
        reason = _reason_act(tool, args, target, policy_text, prior_blocks)
    elif decision == Decision.ASK:
        reason = _reason_ask(tool, args, target, policy_text)
    elif decision == Decision.REFUSE:
        reason = _reason_refuse(tool, args, target, policy_text)
    else:
        reason = f"Proceeding with {tool} on {target}."

    return reason


def _describe_target(tool: str, args: dict) -> str:
    if tool in ("read_file", "write_file", "delete_file"):
        return args.get("path", "unknown path")
    if tool == "send_message":
        return args.get("recipient", "unknown recipient")
    if tool == "update_config":
        return args.get("key", "unknown key")
    if tool == "purchase_item":
        item = args.get("item", "unknown item")
        amount = args.get("amount", "?")
        return f"{item} (${amount})"
    return str(args)


def _reason_act(
    tool: str, args: dict, target: str,
    policy_text: str, prior_blocks: list[str],
) -> str:
    parts = []

    if tool == "read_file":
        parts.append(f"Reading {target}. The policy allows reading files.")
    elif tool == "write_file":
        path = args.get("path", "")
        parts.append(f"Writing to {path}.")
        parts.append(_find_allowing_clause(path, policy_text, tool))
    elif tool == "delete_file":
        path = args.get("path", "")
        parts.append(f"Deleting {path}.")
        parts.append(_find_allowing_clause(path, policy_text, tool))
    elif tool == "send_message":
        recipient = args.get("recipient", "")
        parts.append(f"Sending message to {recipient}.")
        parts.append(_find_allowing_clause(recipient, policy_text, tool))
    elif tool == "update_config":
        key = args.get("key", "")
        parts.append(f"Updating config {key}.")
        parts.append(_find_allowing_clause(key, policy_text, tool))
    elif tool == "purchase_item":
        parts.append(f"Purchasing {target}.")
        parts.append(_find_allowing_clause(target, policy_text, tool))

    if prior_blocks:
        parts.append(
            "Previous actions required approval or were refused, "
            "but this action is authorized. Continuing with remaining work."
        )

    parts.append("This is within my authority. Executing.")
    return " ".join(p for p in parts if p)


def _reason_ask(tool: str, args: dict, target: str, policy_text: str) -> str:
    parts = []
    parts.append(f"This task asks me to {_verb_for_tool(tool)} {target}.")
    parts.append(_find_restricting_clause(target, policy_text, tool))
    parts.append("This requires approval. Escalating to the user.")
    return " ".join(p for p in parts if p)


def _reason_refuse(tool: str, args: dict, target: str, policy_text: str) -> str:
    parts = []
    parts.append(f"This task asks me to {_verb_for_tool(tool)} {target}.")
    parts.append(_find_prohibiting_clause(target, policy_text, tool))
    parts.append("This is prohibited. Refusing this action.")
    return " ".join(p for p in parts if p)


def _verb_for_tool(tool: str) -> str:
    return {
        "read_file": "read",
        "write_file": "write to",
        "delete_file": "delete",
        "send_message": "send a message to",
        "update_config": "update configuration",
        "purchase_item": "purchase",
    }.get(tool, "perform")


def _find_allowing_clause(target: str, policy_text: str, tool: str) -> str:
    """Extract the relevant policy clause that allows this action."""
    sentences = [s.strip() for s in policy_text.split(".") if s.strip()]
    allow_words = {"allowed", "freely", "may", "can", "open", "self-service", "routine"}
    for sentence in sentences:
        lower = sentence.lower()
        if any(w in lower for w in allow_words):
            if _clause_relevant(lower, target, tool):
                return f"The policy states: \"{sentence}.\""
    return ""


def _find_restricting_clause(target: str, policy_text: str, tool: str) -> str:
    sentences = [s.strip() for s in policy_text.split(".") if s.strip()]
    restrict_words = {"approval", "require", "review", "through", "sign-off", "eyes"}
    for sentence in sentences:
        lower = sentence.lower()
        if any(w in lower for w in restrict_words):
            if _clause_relevant(lower, target, tool):
                return f"The policy states: \"{sentence}.\""
    return ""


def _find_prohibiting_clause(target: str, policy_text: str, tool: str) -> str:
    sentences = [s.strip() for s in policy_text.split(".") if s.strip()]
    prohibit_words = {"must not", "prohibited", "never", "cannot", "should not"}
    for sentence in sentences:
        lower = sentence.lower()
        if any(w in lower for w in prohibit_words):
            if _clause_relevant(lower, target, tool):
                return f"The policy states: \"{sentence}.\""
    return ""


def _clause_relevant(clause: str, target: str, tool: str) -> bool:
    """Check if a policy clause is relevant to the given target/tool."""
    target_lower = target.lower()
    target_parts = target_lower.replace("/", " ").replace("_", " ").replace("-", " ").split()

    for part in target_parts:
        if len(part) > 2 and part in clause:
            return True

    tool_keywords = {
        "read_file": ["read"],
        "write_file": ["write", "writ", "creat", "publish"],
        "delete_file": ["delet", "remov", "purg"],
        "send_message": ["messag", "send", "notif", "email", "contact", "communicat"],
        "update_config": ["config", "setting", "system", "project"],
        "purchase_item": ["purchas", "buy", "spend", "cost", "amount"],
    }
    for kw in tool_keywords.get(tool, []):
        if kw in clause:
            return True

    return False
