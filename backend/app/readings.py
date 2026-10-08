"""Every field Hive reports for the heating devices, flattened so a change in any of them shows.

The chain says whether each link works. This keeps the evidence: when the hot water fails,
the log should show what Hive said about the receiver, the hot water and its schedule,
minute by minute, without having known in advance which field would matter.

Each reading is (link, path) -> value, with the value as JSON text so any two can be
compared. Lists stay whole, so editing one day of a schedule is one change.

Pure functions only. No I/O, no clock.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

# Hive node type -> the chain link it belongs to.
DEVICES = {"hub": "hub", "boilermodule": "receiver", "thermostatui": "thermostat"}
PRODUCTS = {"hotwater": "hotwater", "heating": "heating"}

# Bookkeeping, not readings. lastSeen is stale on most devices and ticks on the hub.
IGNORED = {"id", "parent", "created", "sortOrder", "lastSeen"}

# Counters that climb every poll. Only a drop is news: the hub's uptime falling means it
# restarted.
LOGGED_WHEN_FALLING = {("hub", "props.uptime")}

# Whether the last poll reached Hive: "ok", or why not. A single failed poll shows here even
# though it never changes a link's state.
POLL = ("hive", "poll")

# Derived from Hive's own schedule, so a missed scheduled "on" shows next to what Hive did.
HOTWATER_SCHEDULE = "schedule says"
HEATING_SCHEDULE = "schedule target"

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def flatten(nodes: dict[str, Any], local_now: datetime) -> dict[tuple[str, str], str]:
    """Every reading in one poll. local_now is the house's local time, for the schedules."""
    out: dict[tuple[str, str], str] = {}
    for kind, table in (("devices", DEVICES), ("products", PRODUCTS)):
        seen: dict[str, int] = {}
        for node in nodes.get(kind) or []:
            link = table.get(node.get("type"))
            if link is None:
                continue
            # The house has one of each. If that ever changes, keep the extras apart.
            n = seen[link] = seen.get(link, 0) + 1
            prefix = "" if n == 1 else f"[{(node.get('state') or {}).get('name') or n}]."
            _walk(out, link, prefix, {k: v for k, v in node.items() if k not in IGNORED})

    for key in ("status", "holidayMode"):
        if key in nodes:
            out[("hive", key)] = _json(nodes[key])

    hotwater = _product(nodes, "hotwater")
    if hotwater is not None:
        slot = scheduled(hotwater, local_now)
        if slot is not None:
            out[("hotwater", HOTWATER_SCHEDULE)] = _json(slot.get("status") == "ON")
    heating = _product(nodes, "heating")
    if heating is not None:
        slot = scheduled(heating, local_now)
        if slot is not None and "target" in slot:
            out[("heating", HEATING_SCHEDULE)] = _json(slot["target"])
    return out


def scheduled(product: dict, local_now: datetime) -> dict | None:
    """The schedule slot in force at local_now: the last one started today, else yesterday's last."""
    schedule = (product.get("state") or {}).get("schedule") or {}
    minute = local_now.hour * 60 + local_now.minute
    today = DAYS[local_now.weekday()]
    started = [s for s in schedule.get(today) or [] if s.get("start", 0) <= minute]
    if started:
        return max(started, key=lambda s: s["start"]).get("value") or {}
    yesterday = schedule.get(DAYS[local_now.weekday() - 1]) or []
    if yesterday:
        return max(yesterday, key=lambda s: s.get("start", 0)).get("value") or {}
    return None


def changes(
    last: dict[tuple[str, str], str], now: dict[tuple[str, str], str]
) -> list[tuple[str, str, str | None, str]]:
    """(link, path, old, new) for each reading that differs from the last one logged."""
    out = []
    for key, value in now.items():
        old = last.get(key)
        if old == value:
            continue
        if key in LOGGED_WHEN_FALLING and old is not None and _number(value) >= _number(old):
            continue
        out.append((key[0], key[1], old, value))
    return out


def _walk(out: dict, link: str, path: str, value: Any) -> None:
    if isinstance(value, dict) and value:
        for k, v in value.items():
            _walk(out, link, f"{path}{k}.", v)
    else:
        out[(link, path.rstrip("."))] = _json(value)


def _product(nodes: dict, hive_type: str) -> dict | None:
    return next((p for p in nodes.get("products") or [] if p.get("type") == hive_type), None)


def as_value(value: Any) -> str:
    """A reading's value as stored: JSON text, so any two compare as strings."""
    return _json(value)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _number(text: str) -> float:
    try:
        return float(json.loads(text))
    except (TypeError, ValueError):
        return 0.0
