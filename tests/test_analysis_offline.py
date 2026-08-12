import threading

import httpx
import pytest

from src.analysis.chunking import ChunkingError, chunk_transcript
from src.analysis.parsing import parse_meeting_analysis
from src.analysis.providers import (
    AnthropicMessagesProvider,
    CustomAnthropicProvider,
    CustomOpenAIProvider,
    DeepSeekProvider,
    OpenAIChatProvider,
    OpenAIResponsesProvider,
    OpenRouterProvider,
    ProviderError,
    ProviderResponse,
    classify_status,
    provider_from_config,
)
from src.analysis.secrets import CredentialLeaseStore
from src.analysis.service import MeetingAnalysisService
from src.analysis.statuses import ProviderProtocol
from src.analysis.urls import UnsafeProviderURL, validate_provider_url


def _analysis_payload() -> dict[str, object]:
    return {
        "summary": "A bounded summary.",
        "decisions": [],
        "action_items": [],
        "open_questions": [],
        "follow_ups": [],
    }


@pytest.mark.parametrize(
    ("provider_type", "url", "body"),
    [
        (
            OpenAIResponsesProvider,
            "https://api.openai.com/v1",
            {"output_text": '{"summary":"ok"}', "model": "responses-model"},
        ),
        (
            OpenAIChatProvider,
            "https://api.openai.com/v1",
            {
                "choices": [{"message": {"content": '{"summary":"ok"}'}}],
                "model": "chat-model",
            },
        ),
        (
            AnthropicMessagesProvider,
            "https://api.anthropic.com",
            {"content": [{"type": "text", "text": '{"summary":"ok"}'}], "model": "claude"},
        ),
    ],
)
def test_all_protocol_adapters_use_bounded_no_redirect_requests(provider_type, url, body) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = provider_type(api_key="secret", base_url=url, client=client)
    result = provider.generate([{"role": "user", "content": "hello"}], model="m", timeout=2)
    assert result.text == '{"summary":"ok"}'
    assert seen and seen[0].method == "POST"


def test_injected_client_does_not_follow_redirects() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"location": str(request.url)})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIChatProvider(api_key="secret", client=client)
    with pytest.raises(ProviderError) as caught:
        provider.generate([], model="m", timeout=2)
    assert caught.value.code == "invalid_response"
    assert calls == 1


_SECRET = "offline-test-api-key"
_BODY_MARKER = "provider-body-must-not-leak"


def _adapter_cases() -> list[object]:
    return [
        pytest.param(
            "openrouter",
            OpenRouterProvider,
            {"choices": [{"message": {"content": '{"summary":"ok"}'}}], "model": "router"},
            id="openrouter",
        ),
        pytest.param(
            "deepseek",
            DeepSeekProvider,
            {
                "choices": [{"message": {"content": '{"summary":"ok"}'}}],
                "model": "deepseek-v4-flash",
            },
            id="deepseek",
        ),
        pytest.param(
            "custom_openai",
            CustomOpenAIProvider,
            {"choices": [{"message": {"content": '{"summary":"ok"}'}}], "model": "custom"},
            id="custom-openai",
        ),
        pytest.param(
            "custom_anthropic",
            CustomAnthropicProvider,
            {"content": [{"type": "text", "text": '{"summary":"ok"}'}], "model": "claude"},
            id="custom-anthropic",
        ),
    ]


def _provider_factory(provider_type: type, client: httpx.Client):
    return provider_type(
        api_key=_SECRET,
        base_url="https://127.0.0.1",
        allow_local_urls=True,
        client=client,
    )


@pytest.mark.parametrize("provider_name, provider_type, response_body", _adapter_cases())
def test_requested_adapters_succeed_offline(
    provider_name: str, provider_type: type, response_body: dict[str, object]
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=response_body)

    provider = _provider_factory(
        provider_type, httpx.Client(transport=httpx.MockTransport(handler))
    )
    result = provider.generate([{"role": "user", "content": "hello"}], model="requested", timeout=2)

    assert result.text == '{"summary":"ok"}'
    assert requests and requests[0].method == "POST"
    auth_header = requests[0].headers.get("authorization") or requests[0].headers.get("x-api-key")
    assert auth_header in {f"Bearer {_SECRET}", _SECRET}
    assert provider.provider_id == provider_name


@pytest.mark.parametrize("provider_name, provider_type, response_body", _adapter_cases())
@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_requested_adapters_redact_http_errors(
    provider_name: str,
    provider_type: type,
    response_body: dict[str, object],
    status: int,
) -> None:
    del provider_name, response_body

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": _BODY_MARKER, "key": _SECRET})

    provider = _provider_factory(
        provider_type, httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate([], model="requested", timeout=2)

    assert caught.value.code in {"auth_failed", "rate_limited", "provider_unavailable"}
    assert _SECRET not in str(caught.value)
    assert _BODY_MARKER not in str(caught.value)
    assert _SECRET not in repr(caught.value)


@pytest.mark.parametrize("provider_name, provider_type, response_body", _adapter_cases())
@pytest.mark.parametrize("payload", [b"{malformed", b'"a scalar"', b"[1, 2]"])
def test_requested_adapters_reject_malformed_or_non_object_json(
    provider_name: str,
    provider_type: type,
    response_body: dict[str, object],
    payload: bytes,
) -> None:
    del provider_name, response_body

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload, headers={"content-type": "application/json"})

    provider = _provider_factory(
        provider_type, httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate([], model="requested", timeout=2)

    assert caught.value.code in {"invalid_response", "protocol_mismatch"}
    assert _SECRET not in str(caught.value)
    assert payload.decode(errors="replace") not in str(caught.value)


@pytest.mark.parametrize("provider_name, provider_type, response_body", _adapter_cases())
def test_requested_adapters_reject_protocol_mismatch(
    provider_name: str, provider_type: type, response_body: dict[str, object]
) -> None:
    del provider_name, response_body
    mismatch = (
        {"choices": []} if provider_type is not CustomAnthropicProvider else {"content": "text"}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=mismatch)

    provider = _provider_factory(
        provider_type, httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate([], model="requested", timeout=2)

    assert caught.value.code == "protocol_mismatch"
    assert _SECRET not in str(caught.value)


@pytest.mark.parametrize("provider_name, provider_type, response_body", _adapter_cases())
def test_requested_adapters_classify_timeouts_without_leaking_details(
    provider_name: str, provider_type: type, response_body: dict[str, object]
) -> None:
    del provider_name, response_body

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(_BODY_MARKER, request=request)

    provider = _provider_factory(
        provider_type, httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate([], model="requested", timeout=2)

    assert caught.value.code == "timeout"
    assert caught.value.retryable is True
    assert _SECRET not in str(caught.value)
    assert _BODY_MARKER not in str(caught.value)


@pytest.mark.parametrize("provider_name, provider_type, response_body", _adapter_cases())
def test_requested_adapters_do_not_follow_redirects(
    provider_name: str, provider_type: type, response_body: dict[str, object]
) -> None:
    del provider_name, response_body
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(307, headers={"location": "https://attacker.invalid/collect"})

    provider = _provider_factory(
        provider_type, httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(ProviderError) as caught:
        provider.generate([], model="requested", timeout=2)

    assert caught.value.code == "invalid_response"
    assert calls == 1
    assert "attacker.invalid" not in str(caught.value)
    assert _SECRET not in str(caught.value)


@pytest.mark.parametrize(
    ("config_name", "expected_type", "expected_id"),
    [
        ("openrouter", OpenRouterProvider, "openrouter"),
        ("deepseek", DeepSeekProvider, "deepseek"),
        ("custom_openai", CustomOpenAIProvider, "custom_openai"),
        ("custom_anthropic", CustomAnthropicProvider, "custom_anthropic"),
    ],
)
def test_provider_from_config_wires_requested_adapters_offline(
    config_name: str, expected_type: type, expected_id: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if config_name == "custom_anthropic":
            return httpx.Response(
                200, json={"content": [{"type": "text", "text": '{"summary":"ok"}'}]}
            )
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"summary":"ok"}'}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = provider_from_config(
        config_name,
        api_key=_SECRET,
        model="requested",
        base_url="https://127.0.0.1",
        client=client,
        allow_local_urls=True,
    )
    assert isinstance(provider, expected_type)
    assert provider.provider_id == expected_id
    assert provider.generate([], model="requested", timeout=2).text == '{"summary":"ok"}'


def test_provider_from_config_rejects_missing_or_unknown_protocol_without_leaking_key() -> None:
    with pytest.raises(ProviderError) as unknown:
        provider_from_config("not-a-provider", api_key=_SECRET, model="requested")
    assert unknown.value.code == "protocol_mismatch"
    assert _SECRET not in str(unknown.value)


def test_deepseek_provider_uses_official_default_endpoint() -> None:
    provider = provider_from_config("deepseek", api_key=_SECRET, model="deepseek-v4-flash")

    assert isinstance(provider, DeepSeekProvider)
    assert provider.provider_id == "deepseek"
    assert provider.base_url == "https://api.deepseek.com"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "auth_failed"),
        (402, "credits_exhausted"),
        (404, "model_not_found"),
        (408, "timeout"),
        (429, "rate_limited"),
        (503, "provider_unavailable"),
    ],
)
def test_provider_statuses_are_redacted_and_classified(status, code) -> None:
    error = classify_status(status)
    assert error.code == code
    assert "secret" not in str(error).lower()


def test_url_policy_requires_local_opt_in_for_https_and_http() -> None:
    with pytest.raises(UnsafeProviderURL):
        validate_provider_url("https://127.0.0.1:8080")
    assert validate_provider_url("https://127.0.0.1:8080", allow_local=True) == (
        "https://127.0.0.1:8080"
    )
    with pytest.raises(UnsafeProviderURL):
        validate_provider_url("http://127.0.0.1:8080", allow_local=False)
    assert validate_provider_url("http://localhost:8080", allow_local=True).startswith("http://")


def test_lease_is_one_time_and_clears_on_exception() -> None:
    store = CredentialLeaseStore()
    lease_id = store.put("secret")
    with store.lease(lease_id) as secret:
        assert secret == "secret"
    with pytest.raises(KeyError), store.lease(lease_id):
        pass

    second = store.put("second")
    with pytest.raises(RuntimeError), store.lease(second):
        raise RuntimeError("provider failed")
    assert len(store) == 0


def test_lease_consumption_is_atomic_between_threads() -> None:
    store = CredentialLeaseStore()
    lease_id = store.put("secret")
    entered: list[str] = []

    def worker() -> None:
        try:
            with store.lease(lease_id):
                entered.append("ok")
        except KeyError:
            entered.append("missing")

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(entered) == ["missing", "ok"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_chunking_rejects_non_finite_timestamps(value: float) -> None:
    with pytest.raises(ChunkingError):
        chunk_transcript([{"start": value, "end": 1, "text": "x"}])


def test_parser_trusted_metadata_overrides_model_metadata() -> None:
    parsed = parse_meeting_analysis(
        {**_analysis_payload(), "metadata": {"provider_id": "model", "requested_model": "fake"}},
        metadata={
            "provider_id": "adapter",
            "protocol": ProviderProtocol.DEMO,
            "requested_model": "trusted",
            "output_language": "en",
            "prompt_version": "meeting_v1",
            "schema_version": "1",
            "chunk_count": 1,
        },
    )
    assert parsed.metadata.provider_id == "adapter"
    assert parsed.metadata.requested_model == "trusted"


class _FakeProvider:
    provider_id = "demo"
    protocol = ProviderProtocol.DEMO

    def __init__(self, responses: list[ProviderResponse]):
        self.responses = responses
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages, *, model: str, timeout: float) -> ProviderResponse:
        self.calls.append(messages)
        return self.responses.pop(0)


def test_service_processes_chunks_and_bounds_synthesis_and_repair_context() -> None:
    valid = ProviderResponse(structured=_analysis_payload(), actual_model="actual")
    provider = _FakeProvider([valid, valid, ProviderResponse(text="not json"), valid])
    service = MeetingAnalysisService(
        provider,
        model="requested",
        chunk_chars=5,
        max_chunks=2,
        max_transcript_chars=500,
        max_attempts=1,
        sleep=lambda _: None,
    )
    result = service.analyze(
        [{"start": 0, "end": 1, "text": "hello"}, {"start": 1, "end": 2, "text": "world"}],
        duration_seconds=2,
    )
    assert result.metadata.chunk_count == 2
    assert len(provider.calls) == 4  # two chunks, synthesis, one repair
    original = "[0.000-1.000] hello\n[1.000-2.000] world"
    assert provider.calls[-1][0]["content"].count(original) == 1
    assert all("<transcript_data>" in call[0]["content"] for call in provider.calls[:2])
