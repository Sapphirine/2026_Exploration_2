"""DeepSeek client with structured-output helpers."""

from __future__ import annotations

import json
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel

from evoresearcher.config import AppConfig

T = TypeVar("T", bound=BaseModel)


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
        raw = self.text(
            label=label,
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=temperature,
        )
        data = self._extract_json(raw)
        return model.model_validate(data)

    def _extract_json(self, raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))
