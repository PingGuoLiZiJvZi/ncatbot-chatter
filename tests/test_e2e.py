"""End-to-end tests with real LLM API.

Gated by RUN_E2E_LLM=1 environment variable.
These tests make real API calls and may fail due to network/rate limits.
"""
from __future__ import annotations

import os
import pytest

# Skip all tests in this module unless RUN_E2E_LLM is set
pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_E2E_LLM"),
    reason="E2E LLM tests disabled (set RUN_E2E_LLM=1 to enable)",
)


def test_llm_health_check():
    """Verify LLM API is reachable."""
    from conf.loader import ConfigLoader
    from infra.llm_client import LLMClient

    config = ConfigLoader.load("conf/bot.yaml")
    llm = LLMClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
    )
    assert llm.health_check() is True
    llm.close()


def test_concentrate_json_output():
    """Verify LLM returns valid ConcentrateOutput JSON."""
    import json
    from conf.loader import ConfigLoader
    from infra.llm_client import LLMClient
    from infra.llm_schemas import ConcentrateOutput
    from memory.concentrator import ConcentrateJob

    config = ConfigLoader.load("conf/bot.yaml")
    llm = LLMClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
    )

    messages = [
        {"role": "system", "content": "请将以下对话浓缩为JSON。"},
        {"role": "user", "content": "[10:00] Alice: 你好\n[10:01] Bob: 你好呀"},
    ]
    raw = llm.chat_text(messages)
    output = ConcentrateJob._parse_output(raw)
    assert output is not None, f"Failed to parse: {raw[:200]}"
    assert len(output.entries) > 0
    llm.close()


def test_response_json_output():
    """Verify LLM returns valid ResponseOutput JSON."""
    from conf.loader import ConfigLoader
    from infra.llm_client import LLMClient
    from infra.llm_schemas import ResponseAction
    from generation.content_gen import ContentGenerator
    from core.schemas import ActionPlan, ActionType, Priority

    config = ConfigLoader.load("conf/bot.yaml")
    llm = LLMClient(
        api_key=config.api_key,
        base_url=config.base_url,
        model=config.model,
    )

    messages = [
        {"role": "system", "content": "你是一个友好的聊天机器人。请以JSON数组格式回复。"},
        {"role": "user", "content": "你好！"},
    ]
    raw = llm.chat_text(messages)
    # Extract JSON array
    start = raw.rfind("[")
    end = raw.rfind("]") + 1
    assert start >= 0 and end > start, f"No JSON array in: {raw[:200]}"
    import json
    data = json.loads(raw[start:end])
    assert isinstance(data, list) and len(data) > 0
    ra = ResponseAction(**data[0])
    assert ra.content
    llm.close()
