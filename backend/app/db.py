"""SQLite: the Hive device keys, a log of state changes, and when things switched on and off.

Writes happen on a state change or a login, never per poll, so a quiet week costs the
SD card almost nothing. History older than the retention period is deleted once a day.
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

-- Append-only: one row each time any field Hive reports for a heating device changes,
-- plus whether each poll worked. The raw evidence behind the states above.
CREATE TABLE IF NOT EXISTS reading (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    at    TEXT NOT NULL,
    link  TEXT NOT NULL,
    path  TEXT NOT NULL,
    old   TEXT,
    new   TEXT NOT NULL
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

    def record_readings(self, at: datetime, rows: list[tuple[str, str, str | None, str]]) -> None:
        """(link, path, old, new) rows from one poll, in one write."""
        if not rows:
            return
        with self._conn:
            self._conn.executemany(
                "INSERT INTO reading (at, link, path, old, new) VALUES (?, ?, ?, ?, ?)",
                [(at.isoformat(), *row) for row in rows],
            )

    def last_readings(self) -> dict[tuple[str, str], str]:
        """The latest value logged for each reading, so a restart doesn't log them all again."""
        rows = self._conn.execute(
            "SELECT link, path, new FROM reading WHERE id IN (SELECT MAX(id) FROM reading GROUP BY link, path)"
        ).fetchall()
        return {(r["link"], r["path"]): r["new"] for r in rows}

    def readings(self, limit: int = 2000) -> list[dict]:
        """Every link's readings, newest first, for reading the whole picture at once."""
        rows = self._conn.execute(
            "SELECT at, link, path, old, new FROM reading ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def history(self, key: str, limit: int = 500) -> list[dict]:
        """One link's state changes, on/off changes and readings together, newest first."""
        rows = self._conn.execute(
            "SELECT at, kind, old_state, new_state, detail, alert, active, path, old, new FROM ("
            "  SELECT id, at, 'state' AS kind, old_state, new_state, detail, alert,"
            "         NULL AS active, NULL AS path, NULL AS old, NULL AS new"
            "  FROM event WHERE link = ?"
            "  UNION ALL"
            "  SELECT id, at, 'activity', NULL, NULL, NULL, NULL, active, NULL, NULL, NULL"
            "  FROM activity WHERE link = ?"
            "  UNION ALL"
            "  SELECT id, at, 'reading', NULL, NULL, NULL, NULL, NULL, path, old, new"
            "  FROM reading WHERE link = ?"
            ") ORDER BY at DESC, kind ASC, id DESC LIMIT ?",
            (key, key, key, limit),
        ).fetchall()
        entries = []
        for r in rows:
            if r["kind"] == "activity":
                entries.append({"at": r["at"], "kind": "activity", "active": bool(r["active"])})
            elif r["kind"] == "reading":
                entries.append({"at": r["at"], "kind": "reading", "path": r["path"], "old": r["old"], "new": r["new"]})
            else:
                entries.append({k: r[k] for k in ("at", "kind", "old_state", "new_state", "detail", "alert")})
        return entries

    def prune(self, before: datetime) -> int:
        """Delete history older than `before`. Returns how many rows went.

        Each reading's newest row and each link's newest on/off stay whatever their age:
        they are what a restart compares against, so dropping them would log everything
        again as new.
        """
        cutoff = before.isoformat()
        with self._conn:
            gone = self._conn.execute("DELETE FROM event WHERE at < ?", (cutoff,)).rowcount
            gone += self._conn.execute(
                "DELETE FROM activity WHERE at < ? AND id NOT IN (SELECT MAX(id) FROM activity GROUP BY link)",
                (cutoff,),
            ).rowcount
            gone += self._conn.execute(
                "DELETE FROM reading WHERE at < ? AND id NOT IN (SELECT MAX(id) FROM reading GROUP BY link, path)",
                (cutoff,),
            ).rowcount
        return gone

    def close(self) -> None:
        self._conn.close()

