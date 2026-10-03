"""SQLite: the Hive device keys and a log of state changes.

Writes happen on a state change or a login, never per poll, so a quiet week costs the
SD card almost nothing.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .tracker import Transition

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "hive.db"

SCHEMA = """
-- Small named values: the Cognito device keys that let the monitor log in without
-- an SMS code, and the latest refresh token.
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Append-only: one row per confirmed change in a link's state.
CREATE TABLE IF NOT EXISTS event (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TEXT NOT NULL,
    link      TEXT NOT NULL,
    label     TEXT NOT NULL,
    old_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    detail    TEXT NOT NULL,
    alert     TEXT
);
"""


def database_path() -> Path:
    override = os.environ.get("HIVE_DB_PATH")
    return Path(override) if override else DEFAULT_DB_PATH


class Store:
    def __init__(self, path: Path | None = None):
        target = path or database_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        # One connection, used from the event loop thread only.
        self._conn = sqlite3.connect(target, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def get_json(self, key: str) -> dict | None:
        raw = self.get(key)
        return json.loads(raw) if raw else None

    def put(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO kv (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def put_json(self, key: str, value: dict) -> None:
        self.put(key, json.dumps(value))

    def delete(self, key: str) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM kv WHERE key = ?", (key,))

    def record(self, t: Transition) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO event (at, link, label, old_state, new_state, detail, alert) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t.at.isoformat(), t.key, t.label, t.old.value, t.new.value, t.detail, t.alert),
            )

    def recent_events(self, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT at, link, label, old_state, new_state, detail, alert FROM event "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

