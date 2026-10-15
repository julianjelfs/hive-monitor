"""Catch the heating system failing while every device still says it's online.

On 14 October the thermostat stopped sending temperatures and the boiler stopped answering
its schedule and a boost from the app, yet the hub, receiver and thermostat all reported
online with full signal. "Online" isn't enough, so these checks look at whether the system
does what Hive says it should:

- Hot water that should be on, by its schedule, a boost or "always on", hasn't started
  heating water within 5 minutes. Hive's own "working" flag is the receiver saying it is
  firing; on a good day it flips on the same poll as the schedule.
- The house temperature hasn't changed in 2 hours. Hive normally reports a new one every
  few minutes, and the longest gap seen on a good day was 15 minutes. A frozen reading
  means the thermostat isn't getting through.

A failed check turns a healthy link down, so it alerts and recovers through the tracker
like any other fault. A missed hot water run stays down until the boiler is seen heating
water, so the end of a schedule slot doesn't read as "back".

Stateful, because both checks are about time, but no I/O and no clock of its own.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, tzinfo
from typing import Any

from . import readings
from .chain import Link, State

NO_START_AFTER = timedelta(minutes=5)
FROZEN_AFTER = timedelta(hours=2)

HEALTHY = (State.OK, State.WARN)


class Watchdog:
    def __init__(self, tz: tzinfo, temperature: float | None = None, temperature_since: datetime | None = None):
        self._tz = tz
        # The house temperature and when it last changed, carried over from before a restart
        # so a restart doesn't hide a freeze.
        self._temperature = temperature
        self._temperature_since = temperature_since if temperature is not None else None
        # Why hot water should be on, and since when.
        self._wanted: str | None = None
        self._wanted_since: datetime | None = None
        # Set when hot water missed a run; cleared when the boiler is seen heating water.
        self._missed: str | None = None

    def check(self, links: list[Link], nodes: dict[str, Any] | None, now: datetime) -> list[Link]:
        """The links with any failed check marked down. A failed poll checks nothing."""
        if nodes is None:
            return links
        products = nodes.get("products") or []
        faults = {
            "hotwater": self._hotwater(_product(products, "hotwater"), now),
            "thermostat": self._frozen(_product(products, "heating"), now),
        }
        return [
            replace(link, state=State.DOWN, detail=faults[link.key])
            if faults.get(link.key) and link.state in HEALTHY
            else link
            for link in links
        ]

    def _hotwater(self, product: dict | None, now: datetime) -> str | None:
        if product is None:
            return None
        props = product.get("props") or {}
        if "working" not in props:
            return None
        if props["working"] is True:
            self._wanted = self._wanted_since = self._missed = None
            return None

        wanted = _why_on(product, now.astimezone(self._tz))
        if wanted != self._wanted:
            self._wanted, self._wanted_since = wanted, now
        if wanted is not None and now - self._wanted_since >= NO_START_AFTER:
            self._missed = f"{wanted} at {self._local(self._wanted_since)}, but the boiler didn't start heating water"
        return self._missed

    def _frozen(self, product: dict | None, now: datetime) -> str | None:
        temperature = ((product or {}).get("props") or {}).get("temperature")
        if not isinstance(temperature, (int, float)):
            return None
        if temperature != self._temperature or self._temperature_since is None:
            self._temperature, self._temperature_since = temperature, now
            return None
        if now - self._temperature_since < FROZEN_AFTER:
            return None
        return (
            f"House temperature stuck at {temperature:.1f}°C since {self._local(self._temperature_since)}. "
            "The thermostat isn't getting through to the hub."
        )

    def _local(self, when: datetime) -> str:
        return when.astimezone(self._tz).strftime("%a %H:%M")


def _why_on(product: dict, local_now: datetime) -> str | None:
    """Why Hive says hot water should be on now, or None if it shouldn't."""
    state = product.get("state") or {}
    mode = state.get("mode")
    if mode == "BOOST":
        return "Boost started"
    if mode == "MANUAL":
        return "Set to always on"
    if mode == "SCHEDULE" and (readings.scheduled(product, local_now) or {}).get("status") == "ON":
        return "Schedule said on"
    if mode != "OFF" and state.get("status") == "ON":
        return "Hive said on"
    return None


def _product(products: list[dict], hive_type: str) -> dict | None:
    return next((p for p in products if p.get("type") == hive_type), None)
