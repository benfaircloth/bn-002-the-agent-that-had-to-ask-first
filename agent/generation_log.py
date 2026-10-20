from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GenerationRecord:
    scenario_id: str
    step: int
    messages: list[dict]
    raw_response: str
    latency_ms: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    parse_success: bool = True
    parse_error: str | None = None
    model: str | None = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class GenerationLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._records: list[GenerationRecord] = []

    def record(self, rec: GenerationRecord) -> None:
        self._records.append(rec)
        with open(self._path, "a") as f:
            f.write(json.dumps({
                "scenario_id": rec.scenario_id,
                "step": rec.step,
                "messages": rec.messages,
                "raw_response": rec.raw_response,
                "latency_ms": rec.latency_ms,
                "prompt_tokens": rec.prompt_tokens,
                "completion_tokens": rec.completion_tokens,
                "parse_success": rec.parse_success,
                "parse_error": rec.parse_error,
                "model": rec.model,
                "timestamp": rec.timestamp,
            }) + "\n")

    @property
    def records(self) -> list[GenerationRecord]:
        return list(self._records)

    @property
    def parse_failure_rate(self) -> float:
        if not self._records:
            return 0.0
        failures = sum(1 for r in self._records if not r.parse_success)
        return failures / len(self._records)
