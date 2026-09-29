from roticery.config import AccountConfig
from roticery.providers import protocol_for, supports_protocol


def test_known_provider_defaults():
    anthropic = AccountConfig(
        id="a",
        provider="anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key_env="A",
    )
    openrouter = AccountConfig(
        id="o",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="O",
    )
    lmstudio = AccountConfig(
        id="l",
        provider="lmstudio",
        base_url="http://localhost:1234/v1",
        api_key_env=None,
    )

    assert protocol_for(anthropic) == "anthropic"
    assert protocol_for(openrouter) == "both"
    assert protocol_for(lmstudio) == "both"
    assert supports_protocol(openrouter, "openai")
    assert supports_protocol(openrouter, "anthropic")
    assert not supports_protocol(anthropic, "openai")


def test_explicit_protocol_overrides_provider_default():
    account = AccountConfig(
        id="custom",
        provider="anthropic",
        base_url="http://example.test/v1",
        api_key_env=None,
        protocol="both",
    )
    assert protocol_for(account) == "both"
