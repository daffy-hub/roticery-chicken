from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    client_api_key_env: str | None = None


class RotationConfig(BaseModel):
    strategy: Literal["sequential", "round_robin"] = "sequential"
    default_token_threshold: int = 50_000
    retry_statuses: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    default_cooldown_seconds: int = 60


class AccountConfig(BaseModel):
    id: str
    provider: str
    base_url: str
    api_key_env: str | None = None
    api_key: str | None = None
    token_threshold: int | None = None
    cooldown_seconds: int | None = None
    enabled: bool = True
    headers: dict[str, str] = Field(default_factory=dict)
    protocol: Literal["auto", "openai", "anthropic", "both"] = "auto"


class ModelConfig(BaseModel):
    id: str
    owned_by: str = "roticery"


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: str = "data/roticery.db"
    rotation: RotationConfig = Field(default_factory=RotationConfig)
    accounts: list[AccountConfig]
    models: list[ModelConfig] = Field(default_factory=list)

    def account_threshold(self, account: AccountConfig) -> int:
        return account.token_threshold or self.rotation.default_token_threshold

    def account_cooldown(self, account: AccountConfig) -> int:
        if account.cooldown_seconds is not None:
            return account.cooldown_seconds
        return self.rotation.default_cooldown_seconds

    def api_key_for(self, account: AccountConfig) -> str:
        if account.api_key:
            return account.api_key
        if not account.api_key_env:
            return ""
        value = os.getenv(account.api_key_env)
        if value is None:
            raise RuntimeError(
                f"Missing environment variable {account.api_key_env!r} for account {account.id!r}"
            )
        return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(raw)
    if not config.accounts:
        raise ValueError("At least one account must be configured")
    return config
