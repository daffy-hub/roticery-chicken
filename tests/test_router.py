from roticery.config import AccountConfig, AppConfig, RotationConfig
from roticery.router import AccountRouter
from roticery.storage import StateStore


def make_router(tmp_path):
    cfg = AppConfig(
        database=str(tmp_path / "state.db"),
        rotation=RotationConfig(default_token_threshold=10),
        accounts=[
            AccountConfig(id="a", provider="test", base_url="http://a", api_key_env="A"),
            AccountConfig(id="b", provider="test", base_url="http://b", api_key_env="B"),
        ],
    )
    return cfg, StateStore(cfg.database)


def test_default_is_sequential(tmp_path):
    cfg, store = make_router(tmp_path)
    router = AccountRouter(cfg, store)
    assert router.select().config.id == "a"
    assert router.select().config.id == "a"
    store.record_tokens("a", 10)
    assert router.select().config.id == "b"


def test_threshold_excludes_account(tmp_path):
    cfg, store = make_router(tmp_path)
    router = AccountRouter(cfg, store)
    store.record_tokens("a", 10)
    assert router.select().config.id == "b"


def test_round_robin_advances_every_request(tmp_path):
    cfg, store = make_router(tmp_path)
    cfg.rotation.strategy = "round_robin"
    router = AccountRouter(cfg, store)
    assert router.select().config.id == "a"
    assert router.select().config.id == "b"
    assert router.select().config.id == "a"


def test_sequential_stays_on_account_until_threshold(tmp_path):
    cfg, store = make_router(tmp_path)
    router = AccountRouter(cfg, store)
    assert router.select().config.id == "a"
    store.record_tokens("a", 5)
    assert router.select().config.id == "a"
    store.record_tokens("a", 5)
    assert router.select().config.id == "b"
