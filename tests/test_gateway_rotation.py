import httpx
import respx
from fastapi.testclient import TestClient

from roticery.app import create_app
from roticery.config import AccountConfig, AppConfig, RotationConfig


def make_openrouter_account(account_id: str, api_key: str, suffix: str, **kwargs):
    return AccountConfig(
        id=account_id,
        provider="openrouter",
        base_url=f"https://{suffix}.openrouter.test/api/v1",
        api_key=api_key,
        protocol="both",
        **kwargs,
    )


@respx.mock
def test_retries_all_accounts_and_cools_down_retryable_failures(tmp_path):
    config = AppConfig(
        database=str(tmp_path / "state.db"),
        rotation=RotationConfig(
            retry_statuses=[429, 503],
            default_cooldown_seconds=45,
        ),
        accounts=[
            make_openrouter_account("one", "key-one", "one"),
            make_openrouter_account("two", "key-two", "two"),
            make_openrouter_account("three", "key-three", "three"),
        ],
    )
    first = respx.post("https://one.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "rate limited"}})
    )
    second = respx.post("https://two.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(503, json={"error": {"message": "unavailable"}})
    )
    third = respx.post("https://three.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"id": "ok", "choices": [], "usage": {"total_tokens": 4}})
    )

    with TestClient(create_app(config)) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]},
        )
        store = client.app.state.store

    assert response.status_code == 200
    assert [first.call_count, second.call_count, third.call_count] == [1, 1, 1]
    assert first.calls[0].request.headers["authorization"] == "Bearer key-one"
    assert store.get_state("one").disabled_until is not None
    assert store.get_state("two").disabled_until is not None
    assert store.get_state("three").tokens_used == 4


@respx.mock
def test_usage_threshold_moves_sequential_traffic_to_next_account(tmp_path):
    config = AppConfig(
        database=str(tmp_path / "state.db"),
        accounts=[
            make_openrouter_account("one", "key-one", "one", token_threshold=5),
            make_openrouter_account("two", "key-two", "two", token_threshold=50),
        ],
    )
    first = respx.post("https://one.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"id": "first", "choices": [], "usage": {"total_tokens": 5}})
    )
    second = respx.post("https://two.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"id": "second", "choices": [], "usage": {"total_tokens": 2}})
    )

    with TestClient(create_app(config)) as client:
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "hello"}],
        }
        assert client.post("/v1/chat/completions", json=payload).status_code == 200
        assert client.post("/v1/chat/completions", json=payload).status_code == 200

    assert first.call_count == 1
    assert second.call_count == 1


@respx.mock
def test_streaming_request_fails_over_before_sending_chunks(tmp_path):
    config = AppConfig(
        database=str(tmp_path / "state.db"),
        rotation=RotationConfig(retry_statuses=[429], default_cooldown_seconds=45),
        accounts=[
            make_openrouter_account("one", "key-one", "one"),
            make_openrouter_account("two", "key-two", "two"),
        ],
    )
    first = respx.post("https://one.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(429, json={"error": {"message": "rate limited"}})
    )
    second = respx.post("https://two.openrouter.test/api/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )
    )

    with TestClient(create_app(config)) as client:
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "openai/gpt-4o-mini",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )

    assert response.status_code == 200
    assert "hello" in response.text
    assert first.call_count == 1
    assert second.call_count == 1
