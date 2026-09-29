from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AccountState:
    account_id: str
    tokens_used: int
    disabled_until: float | None


class StateStore:
    """Small SQLite state store. Keeps routing state across process restarts."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_state (
                    account_id TEXT PRIMARY KEY,
                    tokens_used INTEGER NOT NULL DEFAULT 0,
                    disabled_until REAL
                );
                CREATE TABLE IF NOT EXISTS router_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    cursor INTEGER NOT NULL DEFAULT 0
                );
                INSERT OR IGNORE INTO router_state(id, cursor) VALUES (1, 0);
                """
            )

    def ensure_accounts(self, account_ids: list[str]) -> None:
        with self._lock, self._connect() as conn:
            for account_id in account_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO account_state(account_id) VALUES (?)",
                    (account_id,),
                )

    def get_state(self, account_id: str) -> AccountState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT account_id, tokens_used, disabled_until FROM account_state WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        if row is None:
            return AccountState(account_id, 0, None)
        return AccountState(row["account_id"], row["tokens_used"], row["disabled_until"])

    def record_tokens(self, account_id: str, tokens: int) -> AccountState:
        tokens = max(0, int(tokens))
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO account_state(account_id) VALUES (?)",
                (account_id,),
            )
            conn.execute(
                "UPDATE account_state SET tokens_used = tokens_used + ? WHERE account_id = ?",
                (tokens, account_id),
            )
            row = conn.execute(
                "SELECT account_id, tokens_used, disabled_until FROM account_state WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        return AccountState(row["account_id"], row["tokens_used"], row["disabled_until"])

    def reset_tokens(self, account_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE account_state SET tokens_used = 0 WHERE account_id = ?",
                (account_id,),
            )

    def disable(self, account_id: str, seconds: int) -> AccountState:
        until = time.time() + max(0, seconds)
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE account_state SET disabled_until = ? WHERE account_id = ?",
                (until, account_id),
            )
            row = conn.execute(
                "SELECT account_id, tokens_used, disabled_until FROM account_state WHERE account_id = ?",
                (account_id,),
            ).fetchone()
        return AccountState(row["account_id"], row["tokens_used"], row["disabled_until"])

    def clear_disable(self, account_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE account_state SET disabled_until = NULL WHERE account_id = ?",
                (account_id,),
            )

    def advance_cursor(self, value: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE router_state SET cursor = ? WHERE id = 1", (value,))

    def get_cursor(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT cursor FROM router_state WHERE id = 1").fetchone()
        return int(row["cursor"])

    def snapshot(self) -> list[AccountState]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT account_id, tokens_used, disabled_until FROM account_state ORDER BY account_id"
            ).fetchall()
        return [AccountState(r["account_id"], r["tokens_used"], r["disabled_until"]) for r in rows]
