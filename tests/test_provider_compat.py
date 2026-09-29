import httpx
import respx
from fastapi.testclient import TestClient

from roticery.app import create_app
from roticery.config import AccountConfig, AppConfig


@respx.mock
def test_anthropic_messages_uses_anthropic_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_KEY", "secret")
    config = AppConfig(
        database=str(tmp_path / "state.db"),
        accounts=[
            AccountConfig(
                id="anthropic",
                provider="anthropic",
                base_url="https://api.anthropic.com/v1",
                api_key_env="ANTHROPIC_KEY",
                protocol="anthropic",
            )
        ],
    )
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 3, "output_tokens": 2},
            },
        )
    )

    with TestClient(create_app(config)) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "claude-test",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    assert response.json()["id"] == "msg_test"
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "secret"
    assert request.headers["anthropic-version"] == "2023-06-01"
    assert "authorization" not in request.headers


@respx.mock
def test_openrouter_can_serve_anthropic_protocol(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY", "secret")
    config = AppConfig(
        database=str(tmp_path / "state.db"),
        accounts=[
            AccountConfig(
                id="openrouter",
                provider="openrouter",
                base_url="https://openrouter.ai/api/v1",
                api_key_env="OPENROUTER_KEY",
                protocol="both",
            )
        ],
    )
    route = respx.post("https://openrouter.ai/api/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msg_or",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "hello"}],
                "usage": {"input_tokens": 4, "output_tokens": 6},
            },
        )
    )

    with TestClient(create_app(config)) as client:
        response = client.post(
            "/v1/messages",
            json={
                "model": "anthropic/claude-test",
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )

    assert response.status_code == 200
    assert route.calls[0].request.headers["authorization"] == "Bearer secret"
