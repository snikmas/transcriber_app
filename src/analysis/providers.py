"""Small provider adapters with one normalized, redacted error boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from .statuses import ProviderProtocol
from .urls import validate_provider_url


@dataclass(frozen=True)
class ProviderResponse:
    text: str | None = None
    structured: dict[str, Any] | None = None
    actual_model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def raw_text(self) -> str | None:
        return self.text


NormalizedProviderResponse = ProviderResponse


class AnalysisProvider(Protocol):
    provider_id: str
    protocol: ProviderProtocol

    def generate(
        self, messages: list[dict[str, str]], *, model: str, timeout: float
    ) -> ProviderResponse: ...


class ProviderError(RuntimeError):
    """Client-safe provider failure; deliberately excludes body, prompt and key."""

    def __init__(self, code: str, message: str | None = None, *, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(message or _MESSAGES.get(code, "Provider request failed."))


_MESSAGES = {
    "auth_failed": "Provider authentication failed.",
    "credits_exhausted": "Provider credits are exhausted.",
    "model_not_found": "The requested provider model was not found.",
    "rate_limited": "Provider rate limit reached; try again later.",
    "timeout": "Provider request timed out.",
    "protocol_mismatch": "Provider response did not match the selected protocol.",
    "provider_unavailable": "Provider is temporarily unavailable.",
    "invalid_response": "Provider returned an invalid response.",
    "unsafe_url": "Provider URL is not allowed.",
}


def classify_status(status: int) -> ProviderError:
    if status in {401, 403}:
        return ProviderError("auth_failed")
    if status == 402:
        return ProviderError("credits_exhausted")
    if status == 404:
        return ProviderError("model_not_found")
    if status == 408:
        return ProviderError("timeout", retryable=True)
    if status == 429:
        return ProviderError("rate_limited", retryable=True)
    if status in {502, 503, 504} or status >= 500:
        return ProviderError("provider_unavailable", retryable=True)
    return ProviderError("provider_unavailable" if status >= 400 else "invalid_response")


def is_retryable_error(error: BaseException) -> bool:
    return isinstance(error, ProviderError) and error.retryable


class _HttpProvider:
    protocol: ProviderProtocol

    def __init__(
        self,
        *,
        provider_id: str,
        api_key: str,
        base_url: str,
        allow_local_urls: bool = False,
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ProviderError("auth_failed", "Provider key is missing.")
        try:
            # Preset hosts are fixed service endpoints and do not need a DNS
            # lookup during object construction (which keeps offline tests and
            # startup deterministic). Custom hosts use full SSRF resolution.
            preset_host = urlsplit(base_url).hostname in {
                "api.openai.com",
                "api.anthropic.com",
                "openrouter.ai",
            }
            self.base_url = validate_provider_url(
                base_url, allow_local=allow_local_urls, resolve_host=not preset_host
            )
        except ValueError as exc:
            raise ProviderError("unsafe_url") from exc
        self.provider_id = provider_id
        self.api_key = api_key
        self._client = client

    def _request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        try:
            if self._client is None:
                response = httpx.request(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    follow_redirects=False,
                )
            else:
                response = self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    follow_redirects=False,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", retryable=True) from exc
        except httpx.RequestError as exc:
            raise ProviderError("provider_unavailable", retryable=True) from exc
        if response.status_code >= 400:
            raise classify_status(response.status_code)
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise ProviderError("invalid_response") from exc
        if not isinstance(data, dict):
            raise ProviderError("protocol_mismatch")
        return data


class DemoAnalysisProvider:
    provider_id = "demo"
    protocol = ProviderProtocol.DEMO

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "deterministic-meeting-v1",
        timeout: float = 60.0,
    ) -> ProviderResponse:
        return ProviderResponse(
            structured={
                "generated_title": "Northstar Studio project update",
                "summary": (
                    "The team reviewed the Northstar Studio release and its local "
                    "transcription workflow."
                ),
                "decisions": [
                    {
                        "description": "Keep durable jobs and timestamped segments in the release.",
                        "source_timestamps": [{"start_seconds": 10.4, "end_seconds": 17.8}],
                    }
                ],
                "action_items": [],
                "open_questions": [],
                "follow_ups": [],
            },
            actual_model=model,
        )


def _content_text(data: Any) -> tuple[str | None, dict[str, Any] | None]:
    if isinstance(data, dict):
        return None, data
    if isinstance(data, str):
        return data, None
    return None, None


class OpenAIResponsesProvider(_HttpProvider):
    protocol = ProviderProtocol.OPENAI_RESPONSES

    def __init__(self, *, api_key: str, base_url: str = "https://api.openai.com/v1", **kwargs: Any):
        super().__init__(provider_id="openai", api_key=api_key, base_url=base_url, **kwargs)

    def generate(
        self, messages: list[dict[str, str]], *, model: str, timeout: float
    ) -> ProviderResponse:
        payload = {"model": model, "input": messages, "text": {"format": {"type": "json_object"}}}
        data = self._request(
            method="POST",
            url=self.base_url + "/responses",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            payload=payload,
            timeout=timeout,
        )
        text = data.get("output_text")
        if not isinstance(text, str):
            parts: list[str] = []
            for item in data.get("output", []):
                for content in item.get("content", []) if isinstance(item, dict) else []:
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        parts.append(content["text"])
            text = "".join(parts) or None
        if text is None and isinstance(data.get("output"), dict):
            text, structured = _content_text(data["output"])
        else:
            structured = None
        return ProviderResponse(
            text=text, structured=structured, actual_model=data.get("model"), usage=_usage(data)
        )


class OpenAIChatProvider(_HttpProvider):
    protocol = ProviderProtocol.OPENAI_CHAT

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        provider_id: str = "openai",
        **kwargs: Any,
    ):
        super().__init__(provider_id=provider_id, api_key=api_key, base_url=base_url, **kwargs)

    def generate(
        self, messages: list[dict[str, str]], *, model: str, timeout: float
    ) -> ProviderResponse:
        payload = {"model": model, "messages": messages, "response_format": {"type": "json_object"}}
        data = self._request(
            method="POST",
            url=self.base_url + "/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            payload=payload,
            timeout=timeout,
        )
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ProviderError("protocol_mismatch")
        message = choices[0].get("message", {})
        text, structured = _content_text(
            message.get("content") if isinstance(message, dict) else None
        )
        return ProviderResponse(
            text=text, structured=structured, actual_model=data.get("model"), usage=_usage(data)
        )


class AnthropicMessagesProvider(_HttpProvider):
    protocol = ProviderProtocol.ANTHROPIC_MESSAGES

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        provider_id: str = "anthropic",
        **kwargs: Any,
    ):
        super().__init__(provider_id=provider_id, api_key=api_key, base_url=base_url, **kwargs)

    def generate(
        self, messages: list[dict[str, str]], *, model: str, timeout: float
    ) -> ProviderResponse:
        system = ""
        user_messages = []
        for message in messages:
            if message.get("role") == "system":
                system += message.get("content", "")
            else:
                user_messages.append(message)
        payload = {"model": model, "max_tokens": 4096, "messages": user_messages}
        if system:
            payload["system"] = system
        data = self._request(
            method="POST",
            url=self.base_url + "/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout=timeout,
        )
        content = data.get("content")
        if not isinstance(content, list):
            raise ProviderError("protocol_mismatch")
        texts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        structured = next(
            (
                item.get("input")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("input"), dict)
            ),
            None,
        )
        return ProviderResponse(
            text="".join(texts) or None,
            structured=structured,
            actual_model=data.get("model"),
            usage=_usage(data),
        )


class OpenRouterProvider(OpenAIChatProvider):
    def __init__(
        self, *, api_key: str, base_url: str = "https://openrouter.ai/api/v1", **kwargs: Any
    ):
        super().__init__(api_key=api_key, base_url=base_url, provider_id="openrouter", **kwargs)


class PackyAPIProvider(OpenAIChatProvider):
    def __init__(self, *, api_key: str, base_url: str, **kwargs: Any):
        super().__init__(api_key=api_key, base_url=base_url, provider_id="packyapi", **kwargs)


class CustomOpenAIProvider(OpenAIChatProvider):
    def __init__(self, *, api_key: str, base_url: str, **kwargs: Any):
        super().__init__(api_key=api_key, base_url=base_url, provider_id="custom_openai", **kwargs)


class CustomAnthropicProvider(AnthropicMessagesProvider):
    def __init__(self, *, api_key: str, base_url: str, **kwargs: Any):
        super().__init__(
            api_key=api_key, base_url=base_url, provider_id="custom_anthropic", **kwargs
        )


CustomOpenAICompatibleProvider = CustomOpenAIProvider
CustomProvider = CustomOpenAIProvider


def _usage(data: dict[str, Any]) -> dict[str, int]:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return {}
    return {
        str(key): int(value)
        for key, value in usage.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }


def provider_from_config(
    provider: str,
    *,
    api_key: str,
    model: str,
    base_url: str | None = None,
    client: httpx.Client | None = None,
    allow_local_urls: bool = False,
) -> AnalysisProvider:
    selected = provider.strip().lower()
    kwargs = {"client": client, "allow_local_urls": allow_local_urls}
    if selected == "demo":
        return DemoAnalysisProvider()
    if selected in {"openai", "openai_responses"}:
        return OpenAIResponsesProvider(
            api_key=api_key, base_url=base_url or "https://api.openai.com/v1", **kwargs
        )
    if selected in {"anthropic", "anthropic_messages"}:
        return AnthropicMessagesProvider(
            api_key=api_key, base_url=base_url or "https://api.anthropic.com", **kwargs
        )
    if selected == "openrouter":
        return OpenRouterProvider(
            api_key=api_key, base_url=base_url or "https://openrouter.ai/api/v1", **kwargs
        )
    if selected == "packyapi":
        if not base_url:
            raise ProviderError("unsafe_url", "PackyAPI base URL must be configured.")
        return PackyAPIProvider(api_key=api_key, base_url=base_url, **kwargs)
    if selected == "custom_openai":
        return CustomOpenAIProvider(api_key=api_key, base_url=base_url or "", **kwargs)
    if selected == "custom_anthropic":
        return CustomAnthropicProvider(api_key=api_key, base_url=base_url or "", **kwargs)
    raise ProviderError("protocol_mismatch", "Unsupported provider protocol.")


create_provider = provider_from_config
