"""DeepSeek client with structured-output helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

import httpx
import pydantic
from pydantic import BaseModel

from evoresearcher.config import AppConfig

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_STRUCTURED_RETRIES = 3
STRICT_RETRY_SUFFIX = (
    "\n\nIMPORTANT: Return ONLY a single valid JSON object that matches the schema. "
    "No prose, no markdown fences, no comments. "
    "Use proper JSON escaping for backslashes, newlines, and quotes inside string values."
)


class LLMClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self._client = httpx.Client(timeout=90)

    def text(
        self,
        *,
        label: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        response = self._client.post(
            self.config.deepseek_base_url,
            headers={
                "Authorization": f"Bearer {self.config.deepseek_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.deepseek_model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()

    def structured(
        self,
        model: type[T],
        *,
        label: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> T:
        schema = json.dumps(model.model_json_schema(), indent=2)
        prompt = (
            f"{user_prompt}\n\n"
            "Return valid JSON only. Do not use markdown fences.\n"
            f"JSON schema:\n{schema}"
        )
        last_exc: Exception | None = None
        for attempt in range(MAX_STRUCTURED_RETRIES):
            attempt_label = label if attempt == 0 else f"{label}_retry{attempt}"
            attempt_system = system_prompt if attempt == 0 else system_prompt + STRICT_RETRY_SUFFIX
            attempt_temp = temperature if attempt == 0 else 0.0
            try:
                raw = self.text(
                    label=attempt_label,
                    system_prompt=attempt_system,
                    user_prompt=prompt,
                    temperature=attempt_temp,
                )
                data = self._extract_json(raw)
                return model.model_validate(data)
            except (json.JSONDecodeError, pydantic.ValidationError) as exc:
                last_exc = exc
                logger.warning(
                    "structured() parse failure on attempt %d/%d (label=%s, model=%s): %s",
                    attempt + 1,
                    MAX_STRUCTURED_RETRIES,
                    label,
                    model.__name__,
                    exc,
                )
                continue
        assert last_exc is not None
        raise last_exc

    def _extract_json(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))
