import os

import httpx
import respx
from fastapi.testclient import TestClient

from roticery.app import create_app
from roticery.config import AccountConfig, AppConfig, ServerConfig


def test_dashboard_routes(tmp_path):
    config_path = tmp_path / "roticery.yaml"
    config = AppConfig(
        server=ServerConfig(host="127.0.0.1", port=2500),
        database=str(tmp_path / "state.db"),
        accounts=[
            AccountConfig(
                id="test-account",
                provider="test",
                base_url="http://example.test/v1",
                api_key_env="TEST_KEY",
            )
        ],
    )

    with TestClient(create_app(config, config_path=config_path)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Rotisserie Chicken" in page.text

        data = client.get("/dashboard/data")
        assert data.status_code == 200
        assert data.json()["accounts"][0]["id"] == "test-account"


def test_dashboard_account_management(tmp_path):
    config_path = tmp_path / "roticery.yaml"
    config = AppConfig(
        server=ServerConfig(host="127.0.0.1", port=2500),
        database=str(tmp_path / "state.db"),
        accounts=[
            AccountConfig(
                id="one",
                provider="test",
                base_url="http://example.test/v1",
                api_key_env="TEST_KEY",
            )
        ],
    )

    with TestClient(create_app(config, config_path=config_path)) as client:
        payload = {
            "id": "two",
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "top-secret-openrouter-key",
            "api_key_env": "TEST_KEY_2",
            "token_threshold": 1000,
            "cooldown_seconds": 30,
            "enabled": True,
            "headers": {},
            "protocol": "both",
        }
        created = client.post("/dashboard/accounts", json=payload)
        assert created.status_code == 200
        assert config_path.exists()
        assert config.accounts[1].api_key == "top-secret-openrouter-key"
        assert client.get("/dashboard/accounts").json()["accounts"][1]["id"] == "two"
        assert "api_key" not in client.get("/dashboard/accounts").json()["accounts"][1]

        updated = dict(payload)
        updated["provider"] = "updated"
        response = client.put("/dashboard/accounts/two", json=updated)
        assert response.status_code == 200
        assert client.get("/dashboard/accounts").json()["accounts"][1]["provider"] == "updated"

        deleted = client.delete("/dashboard/accounts/two")
        assert deleted.status_code == 200
        assert all(a["id"] != "two" for a in client.get("/dashboard/accounts").json()["accounts"])


@respx.mock
def test_dashboard_connection_test(tmp_path, monkeypatch):
    config = AppConfig(
        server=ServerConfig(host="127.0.0.1", port=2500),
        database=str(tmp_path / "state.db"),
        accounts=[
            AccountConfig(
                id="test-account",
                provider="test",
                base_url="http://example.test/v1",
                api_key_env="TEST_KEY",
            )
        ],
    )
    monkeypatch.setenv("TEST_KEY", "secret")
    route = respx.get("http://example.test/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    with TestClient(create_app(config)) as client:
        response = client.post("/dashboard/accounts/test-account/test")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["http_status"] == 200
        assert route.calls[0].request.headers["authorization"] == "Bearer secret"
