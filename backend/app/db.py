"""SQLite: the Hive device keys, a log of state changes, and when things switched on and off.

Writes happen on a state change or a login, never per poll, so a quiet week costs the
SD card almost nothing.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
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

-- Append-only: one row each time hot water or the heating starts or stops running.
CREATE TABLE IF NOT EXISTS activity (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    at     TEXT NOT NULL,
    link   TEXT NOT NULL,
    active INTEGER NOT NULL
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

    def record_activity(self, key: str, at: datetime, active: bool) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO activity (at, link, active) VALUES (?, ?, ?)",
                (at.isoformat(), key, int(active)),
            )

    def last_activity(self) -> dict[str, bool]:
        """Each link's most recent on/off, so a restart doesn't log the same thing again."""
        rows = self._conn.execute(
            "SELECT link, active FROM activity WHERE id IN (SELECT MAX(id) FROM activity GROUP BY link)"
        ).fetchall()
        return {r["link"]: bool(r["active"]) for r in rows}

    def history(self, key: str, limit: int = 200) -> list[dict]:
        """One link's state changes and on/off changes together, newest first."""
        rows = self._conn.execute(
            "SELECT at, kind, old_state, new_state, detail, alert, active FROM ("
            "  SELECT id, at, 'state' AS kind, old_state, new_state, detail, alert, NULL AS active"
            "  FROM event WHERE link = ?"
            "  UNION ALL"
            "  SELECT id, at, 'activity', NULL, NULL, NULL, NULL, active"
            "  FROM activity WHERE link = ?"
            ") ORDER BY at DESC, kind ASC, id DESC LIMIT ?",
            (key, key, limit),
        ).fetchall()
        entries = []
        for r in rows:
            if r["kind"] == "activity":
                entries.append({"at": r["at"], "kind": "activity", "active": bool(r["active"])})
            else:
                entry = dict(r)
                del entry["active"]
                entries.append(entry)
        return entries

    def close(self) -> None:
        self._conn.close()

