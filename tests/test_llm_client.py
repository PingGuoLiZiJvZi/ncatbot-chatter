from unittest.mock import MagicMock, patch
import pytest
from infra.llm_client import LLMClient, LLMError, LLMTimeoutError, LLMRateLimitError


class TestLLMClient:
    def _make_client(self, **kwargs):
        defaults = dict(api_key="sk-test1234abcd", base_url="http://localhost/anthropic", max_retries=1)
        defaults.update(kwargs)
        return LLMClient(**defaults)

    def test_mask_key(self):
        assert LLMClient._mask_key("sk-1234abcd") == "sk-1****abcd"
        assert LLMClient._mask_key("short") == "****"

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_chat_text_success(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="hello world")]
        mock_client.messages.create.return_value = mock_resp

        c = self._make_client()
        result = c.chat_text([{"role": "user", "content": "hi"}])
        assert result == "hello world"

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_chat_text_with_system(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="response")]
        mock_client.messages.create.return_value = mock_resp

        c = self._make_client()
        result = c.chat_text([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hi"},
        ])
        assert result == "response"
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["system"] == "You are helpful."

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_chat_text_empty_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = []
        mock_client.messages.create.return_value = mock_resp

        c = self._make_client()
        result = c.chat_text([{"role": "user", "content": "hi"}])
        assert result == ""

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_chat_text_timeout(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())

        c = self._make_client(max_retries=1)
        with pytest.raises(LLMTimeoutError):
            c.chat_text([{"role": "user", "content": "hi"}])

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_chat_text_rate_limit(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "rate limited"}}
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="rate limited", response=mock_response, body=None
        )

        c = self._make_client(max_retries=1)
        with pytest.raises(LLMRateLimitError):
            c.chat_text([{"role": "user", "content": "hi"}])

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_health_check_success(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="pong")]
        mock_client.messages.create.return_value = mock_resp

        c = self._make_client()
        assert c.health_check() is True

    @patch("infra.llm_client.anthropic.Anthropic")
    def test_health_check_failure(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())

        c = self._make_client(max_retries=1)
        with pytest.raises(LLMTimeoutError):
            c.health_check()


# Import anthropic at module level for exception types in tests
import anthropic
