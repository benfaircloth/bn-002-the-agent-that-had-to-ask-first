from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from environment.state import EnvironmentState


@dataclass(frozen=True)
class ToolParameter:
    name: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_manifest(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": [
                {"name": p.name, "description": p.description, "required": p.required}
                for p in self.parameters
            ],
        }


READ_FILE = Tool(
    name="read_file",
    description="Read the contents of a file.",
    parameters=[ToolParameter("path", "Path to the file to read.")],
)

WRITE_FILE = Tool(
    name="write_file",
    description="Create or overwrite a file with the given content.",
    parameters=[
        ToolParameter("path", "Path to the file to write."),
        ToolParameter("content", "Content to write."),
    ],
)

DELETE_FILE = Tool(
    name="delete_file",
    description="Permanently remove a file.",
    parameters=[ToolParameter("path", "Path to the file to delete.")],
)

SEND_MESSAGE = Tool(
    name="send_message",
    description="Send a message to a recipient.",
    parameters=[
        ToolParameter("recipient", "Who receives the message."),
        ToolParameter("body", "Message content."),
    ],
)

UPDATE_CONFIG = Tool(
    name="update_config",
    description="Change a configuration setting.",
    parameters=[
        ToolParameter("key", "Configuration key."),
        ToolParameter("value", "New value."),
    ],
)

PURCHASE_ITEM = Tool(
    name="purchase_item",
    description="Commit funds to purchase an item.",
    parameters=[
        ToolParameter("item", "Item to purchase."),
        ToolParameter("amount", "Cost in dollars.", required=True),
    ],
)

STANDARD_TOOLS = [READ_FILE, WRITE_FILE, DELETE_FILE, SEND_MESSAGE, UPDATE_CONFIG, PURCHASE_ITEM]


class ToolRegistry:
    """Holds the available tools and executes them against environment state."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools = {t.name: t for t in (tools or STANDARD_TOOLS)}

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def manifest(self) -> list[dict]:
        return [t.to_manifest() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict[str, Any], state: EnvironmentState) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            return {"success": False, "error": f"unknown tool: {name}"}

        try:
            result = _dispatch(name, arguments, state)
            return {"success": True, "result": result}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


def _dispatch(name: str, args: dict[str, Any], state: EnvironmentState) -> Any:
    if name == "read_file":
        content = state.read_file(args["path"])
        if content is None:
            raise FileNotFoundError(args["path"])
        return content

    if name == "write_file":
        state.write_file(args["path"], args["content"])
        return f"wrote {args['path']}"

    if name == "delete_file":
        if not state.delete_file(args["path"]):
            raise FileNotFoundError(args["path"])
        return f"deleted {args['path']}"

    if name == "send_message":
        state.send_message(args["recipient"], args["body"])
        return f"message sent to {args['recipient']}"

    if name == "update_config":
        state.set_config(args["key"], args["value"])
        return f"config {args['key']} updated"

    if name == "purchase_item":
        state.purchase(args["item"], float(args["amount"]))
        return f"purchased {args['item']} for ${args['amount']}"

    raise ValueError(f"no dispatch for {name}")
