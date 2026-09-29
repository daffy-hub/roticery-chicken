from fastapi.testclient import TestClient

from roticery.app import create_app
from roticery.config import AccountConfig, AppConfig, ServerConfig


def test_dashboard_routes(tmp_path):
    config = AppConfig(
        server=ServerConfig(host="127.0.0.1", port=2500),
        database=str(tmp_path / "state.db"),
        accounts=[
            AccountConfig(
                id="test-account",
                provider="test",
                base_url="http://example.test",
                api_key_env="TEST_KEY",
            )
        ],
    )

    with TestClient(create_app(config)) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Roticery Chicken" in page.text

        data = client.get("/dashboard/data")
        assert data.status_code == 200
        payload = data.json()
        assert payload["strategy"] == "sequential"
        assert payload["accounts"][0]["id"] == "test-account"
