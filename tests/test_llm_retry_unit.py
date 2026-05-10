"""Tests for LLMClient.structured() retry on JSON parse / validation failures.

This is the P3 robustness fix: the pilot saw 3 hard failures (idx-16 ×1,
idx-62 ×2) where DeepSeek produced malformed JSON and `_extract_json` raised
on the first attempt. The fix retries up to MAX_STRUCTURED_RETRIES with a
stricter system prompt and temperature=0 on subsequent attempts.
"""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from evoresearcher.llm import LLMClient, MAX_STRUCTURED_RETRIES, STRICT_RETRY_SUFFIX


class _SmallSchema(BaseModel):
    winner_id: str
    rationale: str


class StubLLM(LLMClient):
    """Subclass that bypasses HTTP and returns canned `text()` responses in order."""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def text(self, *, label, system_prompt, user_prompt, temperature=0.2):
        self.calls.append(
            {"label": label, "system_prompt": system_prompt, "temperature": temperature}
        )
        if not self.responses:
            raise RuntimeError("ran out of stubbed responses")
        return self.responses.pop(0)


def test_structured_returns_on_first_attempt():
    client = StubLLM(['{"winner_id": "a", "rationale": "ok"}'])
    result = client.structured(
        _SmallSchema,
        label="judge",
        system_prompt="sys",
        user_prompt="usr",
    )
    assert result.winner_id == "a"
    assert len(client.calls) == 1
    assert client.calls[0]["temperature"] == 0.2  # original temp preserved
    assert client.calls[0]["label"] == "judge"


def test_structured_retries_on_json_decode_error_and_succeeds():
    client = StubLLM(["not json at all", '{"winner_id": "b", "rationale": "ok"}'])
    result = client.structured(
        _SmallSchema,
        label="judge",
        system_prompt="sys",
        user_prompt="usr",
    )
    assert result.winner_id == "b"
    assert len(client.calls) == 2
    # Retry uses temperature=0 and stricter prompt suffix.
    assert client.calls[1]["temperature"] == 0.0
    assert STRICT_RETRY_SUFFIX in client.calls[1]["system_prompt"]
    assert client.calls[1]["label"] == "judge_retry1"


def test_structured_retries_on_validation_error():
    # JSON is well-formed but rationale is missing -> pydantic.ValidationError
    client = StubLLM(['{"winner_id": "a"}', '{"winner_id": "a", "rationale": "ok"}'])
    result = client.structured(
        _SmallSchema,
        label="judge",
        system_prompt="sys",
        user_prompt="usr",
    )
    assert result.rationale == "ok"
    assert len(client.calls) == 2


def test_structured_raises_after_max_retries():
    client = StubLLM(["garbage"] * MAX_STRUCTURED_RETRIES)
    with pytest.raises(json.JSONDecodeError):
        client.structured(
            _SmallSchema,
            label="judge",
            system_prompt="sys",
            user_prompt="usr",
        )
    assert len(client.calls) == MAX_STRUCTURED_RETRIES


def test_structured_extracts_brace_block_without_retry():
    # _extract_json's regex fallback should handle this without consuming a retry
    raw = "Here is the result: {\"winner_id\": \"a\", \"rationale\": \"ok\"} thanks!"
    client = StubLLM([raw])
    result = client.structured(
        _SmallSchema,
        label="judge",
        system_prompt="sys",
        user_prompt="usr",
    )
    assert result.winner_id == "a"
    assert len(client.calls) == 1


def test_structured_replays_pilot_style_failure():
    """Reproduce the pilot's failure shape: malformed JSON with embedded backslash escape, then a clean retry."""
    bad = '{"winner_id": "idea-3", "rationale": "see fig \\$L_0\\$\\n"}'
    good = '{"winner_id": "idea-3", "rationale": "see fig $L_0$"}'
    # Confirm the bad one really does fail to parse.
    with pytest.raises(json.JSONDecodeError):
        json.loads(bad)
    client = StubLLM([bad, good])
    result = client.structured(
        _SmallSchema,
        label="judge",
        system_prompt="sys",
        user_prompt="usr",
    )
    assert result.winner_id == "idea-3"
    assert len(client.calls) == 2
