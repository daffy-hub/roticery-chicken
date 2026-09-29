from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from .config import AccountConfig, AppConfig


def save_config(path: str | Path, config: AppConfig) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump(exclude_none=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def find_account(config: AppConfig, account_id: str) -> AccountConfig:
    for account in config.accounts:
        if account.id == account_id:
            return account
    raise KeyError(account_id)


def upsert_account(config: AppConfig, account: AccountConfig) -> None:
    for index, existing in enumerate(config.accounts):
        if existing.id == account.id:
            config.accounts[index] = account
            return
    config.accounts.append(account)


def remove_account(config: AppConfig, account_id: str) -> None:
    remaining = [account for account in config.accounts if account.id != account_id]
    if not remaining:
        raise ValueError("At least one account must remain configured")
    config.accounts = remaining
