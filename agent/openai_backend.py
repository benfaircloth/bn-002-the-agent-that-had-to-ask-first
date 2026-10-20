from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv

from agent.generation_log import GenerationLog, GenerationRecord

load_dotenv()


class OpenAIBackend:
    """Backend adapter that calls any OpenAI-compatible chat completion API.

    Works with Together AI, vLLM, Ollama, or any provider that implements
    the OpenAI chat completions interface. Set OPENAI_BASE_URL to point
    at your provider.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 1024,
        generation_log: GenerationLog | None = None,
        scenario_id: str = "",
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            base_url=os.environ.get("OPENAI_BASE_URL"),
        )
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._log = generation_log
        self._scenario_id = scenario_id
        self._step = 0

    @property
    def scenario_id(self) -> str:
        return self._scenario_id

    @scenario_id.setter
    def scenario_id(self, value: str) -> None:
        self._scenario_id = value
        self._step = 0

    def complete(self, messages: list[dict]) -> str:
        self._step += 1
        t0 = time.monotonic()

        response = self._client.chat.completions.create(
            messages=messages,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            response_format={"type": "json_object"},
        )

        latency_ms = (time.monotonic() - t0) * 1000

        content = ""
        prompt_tokens = None
        completion_tokens = None

        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content or ""
        if response.usage:
            prompt_tokens = getattr(response.usage, "prompt_tokens", None)
            completion_tokens = getattr(response.usage, "completion_tokens", None)

        parse_success = True
        parse_error = None
        try:
            json.loads(content)
        except (json.JSONDecodeError, TypeError) as e:
            parse_success = False
            parse_error = str(e)

        if self._log:
            self._log.record(GenerationRecord(
                scenario_id=self._scenario_id,
                step=self._step,
                messages=messages,
                raw_response=content,
                latency_ms=round(latency_ms, 1),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                parse_success=parse_success,
                parse_error=parse_error,
                model=self._model,
            ))

        return content
