from __future__ import annotations

import logging
import time
from typing import Any

from openai import OpenAI, APITimeoutError, APIStatusError, RateLimitError

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
        base_url: str,
        model: str = "deepseek-chat",
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
        self._client = OpenAI(
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

    def chat_text(self, messages: list[dict[str, Any]]) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(
                    "LLM request attempt=%d model=%s key=%s",
                    attempt, self.model, self._api_key_masked,
                )
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                text = resp.choices[0].message.content or ""
                logger.debug("LLM response length=%d", len(text))
                return text
            except APITimeoutError as e:
                last_exc = e
                logger.warning("LLM timeout attempt=%d: %s", attempt, e)
            except RateLimitError as e:
                last_exc = e
                logger.warning("LLM rate limit attempt=%d: %s", attempt, e)
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
            except APIStatusError as e:
                last_exc = e
                logger.error("LLM API error attempt=%d status=%d: %s", attempt, e.status_code, e)
                if e.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise LLMError(f"LLM API error {e.status_code}: {e}") from e
            except Exception as e:
                raise LLMError(f"LLM unexpected error: {e}") from e

        if isinstance(last_exc, APITimeoutError):
            raise LLMTimeoutError(f"LLM timeout after {self.max_retries} retries") from last_exc
        if isinstance(last_exc, RateLimitError):
            raise LLMRateLimitError(f"LLM rate limited after {self.max_retries} retries") from last_exc
        raise LLMError(f"LLM failed after {self.max_retries} retries") from last_exc

    def health_check(self) -> bool:
        try:
            self.chat_text([{"role": "user", "content": "ping"}])
            return True
        except LLMError:
            raise
