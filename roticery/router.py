from __future__ import annotations

import time
from dataclasses import dataclass

from .config import AccountConfig, AppConfig
from .providers import supports_protocol
from .storage import AccountState, StateStore


@dataclass(frozen=True)
class SelectedAccount:
    config: AccountConfig
    state: AccountState


class AccountRouter:
    def __init__(self, config: AppConfig, store: StateStore):
        self.config = config
        self.store = store
        self.store.ensure_accounts([a.id for a in config.accounts])

    def _eligible(self, account: AccountConfig, state: AccountState) -> bool:
        if not account.enabled:
            return False
        if state.tokens_used >= self.config.account_threshold(account):
            return False
        if state.disabled_until is not None and state.disabled_until > time.time():
            return False
        return True

    def select(self, protocol: str | None = None) -> SelectedAccount:
        accounts = self.config.accounts
        if not accounts:
            raise RuntimeError("No accounts configured")

        start = self.store.get_cursor() % len(accounts)
        order = list(range(start, len(accounts))) + list(range(0, start))

        for idx in order:
            account = accounts[idx]
            state = self.store.get_state(account.id)
            if self._eligible(account, state) and (protocol is None or supports_protocol(account, protocol)):
                if self.config.rotation.strategy == "round_robin":
                    # Round-robin advances after every successful selection.
                    self.store.advance_cursor((idx + 1) % len(accounts))
                else:
                    # Sequential mode keeps the cursor on the current account until
                    # its threshold/cooldown makes it ineligible. If the cursor points
                    # at an exhausted account, selection below moves it to the next one.
                    self.store.advance_cursor(idx)
                return SelectedAccount(account, state)

        raise RuntimeError("No eligible upstream accounts remain")
