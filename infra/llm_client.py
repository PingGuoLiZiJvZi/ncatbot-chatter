from __future__ import annotations

import logging
import time
from typing import Any

import os

import anthropic

# Remove env vars so anthropic SDK uses only the api_key passed to constructor
for _env in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
    os.environ.pop(_env, None)

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/anthropic",
        model: str = "deepseek-v4-pro",
        temperature: float = 1.3,
        max_tokens: int = 2048,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self._api_key_masked = self._mask_key(api_key)

    @staticmethod
    def _mask_key(key: str) -> str:
        if len(key) <= 8:
            return "****"
        return key[:4] + "****" + key[-4:]

    def chat_text(self, messages: list[dict[str, Any]], system: str = "") -> str:
        last_exc: Exception | None = None

        # Separate system message from conversation messages
        system_text = system
        conv_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
            else:
                conv_messages.append(msg)

        # Ensure messages alternate user/assistant and start with user
        if not conv_messages or conv_messages[0].get("role") != "user":
            conv_messages.insert(0, {"role": "user", "content": "(no input)"})

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "LLM request attempt=%d model=%s key=%s",
                    attempt, self.model, self._api_key_masked,
                )
                kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": conv_messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                }
                if system_text:
                    kwargs["system"] = system_text

                resp = self._client.messages.create(**kwargs)
                text = ""
                for block in resp.content:
                    if hasattr(block, "text"):
                        text = block.text
                        break
                logger.debug("LLM response length=%d", len(text))
                return text
            except anthropic.APITimeoutError as e:
                last_exc = e
                logger.warning("LLM timeout attempt=%d: %s", attempt, e)
            except anthropic.RateLimitError as e:
                last_exc = e
                logger.warning("LLM rate limit attempt=%d: %s", attempt, e)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
            except anthropic.APIStatusError as e:
                last_exc = e
                logger.error("LLM API error attempt=%d status=%d: %s", attempt, e.status_code, e)
                if e.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(f"LLM API error {e.status_code}: {e}") from e
            except Exception as e:
                raise LLMError(f"LLM unexpected error: {e}") from e

        if isinstance(last_exc, anthropic.APITimeoutError):
            raise LLMTimeoutError(f"LLM timeout after {self.max_retries} retries") from last_exc
        if isinstance(last_exc, anthropic.RateLimitError):
            raise LLMRateLimitError(f"LLM rate limited after {self.max_retries} retries") from last_exc
        raise LLMError(f"LLM failed after {self.max_retries} retries") from last_exc

    def health_check(self) -> bool:
        try:
            self.chat_text([{"role": "user", "content": "ping"}])
            return True
        except LLMError:
            raise

    def close(self) -> None:
        pass
