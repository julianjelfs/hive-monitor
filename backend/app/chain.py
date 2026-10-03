"""Turn one poll's raw observations into the status of each link in the chain.

The chain runs from the Pi out to the boiler:

    Pi → internet → Hive cloud → hub → boiler receiver → hot water / heating
                                     ↘ wall thermostat

Each link depends on the one before it. When a link is down, everything behind it
is unknown rather than down: the cloud's picture of a receiver behind an offline hub
is stale, and calling it broken would send two alerts for one fault. So the first
red link is the fault, and that is the one that alerts.

Pure functions only. No I/O, no clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class State(str, Enum):
    OK = "ok"
    WARN = "warn"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Link:
    key: str
    label: str
    state: State
    detail: str


@dataclass(frozen=True)
class Observation:
    """What one poll saw.

    nodes is the parsed body of Hive's nodes/all endpoint, or None if the call failed,
    in which case hive_error says why. internet is only consulted when the Hive call
    failed: a successful Hive call proves the internet works.
    """

    nodes: dict[str, Any] | None
    hive_error: str | None = None
    internet: bool = True


# key, label, the key this link depends on. Order is display order.
CHAIN: list[tuple[str, str, str | None]] = [
    ("internet", "Pi to internet", None),
    ("hive", "Hive cloud", "internet"),
    ("hub", "Hub to Hive cloud", "hive"),
    ("receiver", "Hub to boiler receiver", "hub"),
    ("hotwater", "Hot water", "receiver"),
    ("heating", "Heating", "receiver"),
    ("thermostat", "Hub to wall thermostat", "hub"),
]

LABELS = {key: label for key, label, _ in CHAIN}

LOW_BATTERY = 20


def assess(obs: Observation) -> list[Link]:
    own = {
        "internet": _internet(obs),
        "hive": _hive(obs),
    }
    if obs.nodes is not None:
        devices = obs.nodes.get("devices") or []
        products = obs.nodes.get("products") or []
        own.update(
            hub=_devices(devices, "hub", "hub"),
            receiver=_devices(devices, "boilermodule", "boiler receiver"),
            thermostat=_devices(devices, "thermostatui", "wall thermostat"),
            hotwater=_hotwater(products),
            heating=_heating(products),
        )

    links: dict[str, Link] = {}
    for key, label, parent in CHAIN:
        upstream = links.get(parent) if parent else None
        if upstream is not None and upstream.state in (State.DOWN, State.UNKNOWN):
            links[key] = Link(key, label, State.UNKNOWN, f"Can't see past {upstream.label.lower()}")
            continue
        state, detail = own[key]
        links[key] = Link(key, label, state, detail)
    return [links[key] for key, _, _ in CHAIN]


def _internet(obs: Observation) -> tuple[State, str]:
    if obs.nodes is not None or obs.internet:
        return State.OK, "Connected"
    return State.DOWN, "The Pi can't reach the internet. Broadband is probably down."


def _hive(obs: Observation) -> tuple[State, str]:
    if obs.nodes is not None:
        return State.OK, "Logged in and answering"
    return State.DOWN, obs.hive_error or "No answer from Hive"


def _devices(devices: list[dict], hive_type: str, name: str) -> tuple[State, str]:
    found = [d for d in devices if d.get("type") == hive_type]
    if not found:
        return State.DOWN, f"No {name} in the Hive account"

    offline = [d for d in found if not (d.get("props") or {}).get("online")]
    if offline:
        names = ", ".join(_name(d, name) for d in offline)
        return State.DOWN, f"Offline: {names}"

    notes = []
    state = State.OK
    for d in found:
        props = d.get("props") or {}
        bits = []
        if props.get("model"):
            bits.append(props["model"])
        if isinstance(props.get("signal"), (int, float)):
            bits.append(f"signal {props['signal']}%")
        if props.get("power") == "battery" and isinstance(props.get("battery"), (int, float)):
            bits.append(f"battery {props['battery']}%")
            if props["battery"] < LOW_BATTERY:
                state = State.WARN
        notes.append(", ".join(bits))
    return state, "Online" + (f" ({'; '.join(n for n in notes if n)})" if any(notes) else "")


def _name(device: dict, fallback: str) -> str:
    return (device.get("state") or {}).get("name") or fallback


def _product(products: list[dict], hive_type: str) -> dict | None:
    return next((p for p in products if p.get("type") == hive_type), None)


def _hotwater(products: list[dict]) -> tuple[State, str]:
    product = _product(products, "hotwater")
    if product is None:
        return State.DOWN, "No hot water control in the Hive account"
    props = product.get("props") or {}
    state = product.get("state") or {}
    if not props.get("online"):
        return State.DOWN, "Hive reports hot water control offline"

    mode = state.get("mode")
    on_now = state.get("status") == "ON" or props.get("working") is True
    now = "heating water now" if on_now else "not heating right now"
    if mode == "OFF":
        return State.WARN, "Switched off. No hot water until it's back on schedule."
    if mode == "BOOST":
        return State.OK, f"Boost, {now}"
    if mode == "MANUAL":
        return State.OK, f"Always on, {now}"
    return State.OK, f"On schedule, {now}"


def _heating(products: list[dict]) -> tuple[State, str]:
    product = _product(products, "heating")
    if product is None:
        return State.DOWN, "No heating control in the Hive account"
    props = product.get("props") or {}
    state = product.get("state") or {}
    if not props.get("online"):
        return State.DOWN, "Hive reports heating control offline"

    bits = []
    if isinstance(props.get("temperature"), (int, float)):
        bits.append(f"{props['temperature']:.1f}°C in the house")
    if isinstance(state.get("target"), (int, float)):
        bits.append(f"target {state['target']:.1f}°C")
    mode = {"SCHEDULE": "on schedule", "MANUAL": "manual", "OFF": "off", "BOOST": "boost"}.get(
        state.get("mode") or "", "mode unknown"
    )
    bits.append(mode)
    if props.get("working") is True:
        bits.append("boiler firing")
    return State.OK, ", ".join(bits).capitalize() if bits else "Online"
