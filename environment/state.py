from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileEntry:
    path: str
    content: str = ""
    category: str = "general"


class EnvironmentState:
    """Simulated workspace the agent operates on.

    Every mutation is recorded so the full history is inspectable.
    """

    def __init__(self, files: list[FileEntry] | None = None) -> None:
        self._files: dict[str, FileEntry] = {}
        self._messages: list[dict[str, str]] = []
        self._config: dict[str, str] = {}
        self._purchases: list[dict] = []
        self._history: list[dict] = []

        for f in files or []:
            self._files[f.path] = f

    def list_files(self) -> list[str]:
        return sorted(self._files)

    def read_file(self, path: str) -> str | None:
        entry = self._files.get(path)
        return entry.content if entry else None

    def file_category(self, path: str) -> str | None:
        entry = self._files.get(path)
        return entry.category if entry else None

    def write_file(self, path: str, content: str, category: str = "general") -> None:
        self._files[path] = FileEntry(path=path, content=content, category=category)
        self._history.append({"action": "write_file", "path": path})

    def delete_file(self, path: str) -> bool:
        if path in self._files:
            del self._files[path]
            self._history.append({"action": "delete_file", "path": path})
            return True
        return False

    def send_message(self, recipient: str, body: str) -> None:
        msg = {"recipient": recipient, "body": body}
        self._messages.append(msg)
        self._history.append({"action": "send_message", "recipient": recipient})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def get_config(self, key: str) -> str | None:
        return self._config.get(key)

    def set_config(self, key: str, value: str) -> None:
        self._config[key] = value
        self._history.append({"action": "set_config", "key": key})

    def purchase(self, item: str, amount: float) -> None:
        record = {"item": item, "amount": amount}
        self._purchases.append(record)
        self._history.append({"action": "purchase", "item": item, "amount": amount})

    def get_purchases(self) -> list[dict]:
        return list(self._purchases)

    @property
    def history(self) -> list[dict]:
        return list(self._history)
