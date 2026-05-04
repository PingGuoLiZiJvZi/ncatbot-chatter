from unittest.mock import MagicMock, patch
import pytest
from infra.llm_client import LLMClient, LLMError, LLMTimeoutError, LLMRateLimitError


class TestLLMClient:
    def _make_client(self, **kwargs):
        defaults = dict(api_key="sk-test1234abcd", base_url="http://localhost/v1", max_retries=1)
        defaults.update(kwargs)
        return LLMClient(**defaults)

    def test_mask_key(self):
        assert LLMClient._mask_key("sk-1234abcd") == "sk-1****abcd"
        assert LLMClient._mask_key("short") == "****"

    @patch("infra.llm_client.OpenAI")
    def test_chat_text_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="hello world"))]
        mock_client.chat.completions.create.return_value = mock_resp

        c = self._make_client()
        result = c.chat_text([{"role": "user", "content": "hi"}])
        assert result == "hello world"

    @patch("infra.llm_client.OpenAI")
    def test_chat_text_empty_response(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content=None))]
        mock_client.chat.completions.create.return_value = mock_resp

        c = self._make_client()
        result = c.chat_text([{"role": "user", "content": "hi"}])
        assert result == ""

    @patch("infra.llm_client.OpenAI")
    def test_chat_text_timeout(self, mock_openai_cls):
        from openai import APITimeoutError
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())

        c = self._make_client(max_retries=1)
        with pytest.raises(LLMTimeoutError):
            c.chat_text([{"role": "user", "content": "hi"}])

    @patch("infra.llm_client.OpenAI")
    def test_chat_text_rate_limit(self, mock_openai_cls):
        from openai import RateLimitError
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "rate limited"}}
        mock_client.chat.completions.create.side_effect = RateLimitError(
            message="rate limited", response=mock_response, body=None
        )

        c = self._make_client(max_retries=1)
        with pytest.raises(LLMRateLimitError):
            c.chat_text([{"role": "user", "content": "hi"}])

    @patch("infra.llm_client.OpenAI")
    def test_health_check_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="pong"))]
        mock_client.chat.completions.create.return_value = mock_resp

        c = self._make_client()
        assert c.health_check() is True

    @patch("infra.llm_client.OpenAI")
    def test_health_check_failure(self, mock_openai_cls):
        from openai import APITimeoutError
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())

        c = self._make_client(max_retries=1)
        with pytest.raises(LLMTimeoutError):
            c.health_check()
