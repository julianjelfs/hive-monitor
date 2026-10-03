"""The polling loop: look at Hive, work out each link's state, alert on real changes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Protocol

import httpx

from .chain import Link, Observation, State, assess
from .db import Store
from .hive import HiveNeedsSetup
from .notify import Notifier, message_for
from .tracker import Tracker

log = logging.getLogger(__name__)

# Two independent places, so one of them having a bad day doesn't look like broadband down.
INTERNET_PROBES = ("https://1.1.1.1/cdn-cgi/trace", "https://www.gstatic.com/generate_204")


class HiveSource(Protocol):
    async def fetch(self) -> dict[str, Any]: ...


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Monitor:
    def __init__(
        self,
        source: HiveSource,
        store: Store,
        notifier: Notifier,
        internet: Callable[[], Awaitable[bool]],
        heartbeat: Callable[[], Awaitable[None]] | None = None,
        interval: float = 60,
        confirm_after: int = 2,
        clock: Callable[[], datetime] = utcnow,
    ):
        self._source = source
        self._store = store
        self.notifier = notifier
        self._internet = internet
        self._heartbeat = heartbeat
        self._interval = interval
        self._clock = clock
        self.tracker = Tracker(confirm_after=confirm_after)
        self.links: list[Link] = []
        self.checked_at: datetime | None = None
        self._wake = asyncio.Event()

    async def poll_once(self) -> list[Link]:
        nodes = None
        error = None
        try:
            nodes = await self._source.fetch()
        except HiveNeedsSetup as err:
            error = str(err)
        except httpx.HTTPStatusError as err:
            error = f"Hive answered {err.response.status_code}"
        except Exception as err:  # noqa: BLE001 - any failure to read Hive is a down link
            error = f"Couldn't reach Hive ({type(err).__name__})"
            log.info("hive fetch failed: %r", err)

        internet = True if nodes is not None else await self._internet()
        links = assess(Observation(nodes=nodes, hive_error=error, internet=internet))
        now = self._clock()

        for t in self.tracker.update(links, now):
            log.info("%s: %s -> %s (%s)", t.key, t.old.value, t.new.value, t.detail)
            # A healthy link at startup is not news; anything else is.
            if not (t.first and t.new == State.OK):
                self._store.record(t)
            if t.alert:
                title, body, urgent = message_for(t)
                try:
                    await self.notifier.send(title, body, urgent)
                except Exception as err:  # noqa: BLE001 - a failed push must not stop the loop
                    log.warning("push failed: %r", err)

        self.links, self.checked_at = links, now

        if internet and self._heartbeat:
            try:
                await self._heartbeat()
            except Exception as err:  # noqa: BLE001
                log.info("heartbeat failed: %r", err)
        return links

    async def run(self) -> None:
        while True:
            try:
                await self.poll_once()
            except Exception:  # noqa: BLE001 - keep watching whatever happens
                log.exception("poll failed")
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass

    def check_now(self) -> None:
        self._wake.set()

    def snapshot(self) -> dict[str, Any]:
        links = []
        for link in self.links:
            confirmed = self.tracker.confirmed(link.key) == link.state
            links.append(
                {
                    "key": link.key,
                    "label": link.label,
                    "state": link.state.value,
                    "detail": link.detail,
                    "since": _iso(self.tracker.since(link.key)) if confirmed else None,
                }
            )
        broken = next((l for l in self.links if l.state == State.DOWN), None)
        return {
            "checked_at": _iso(self.checked_at),
            "interval": self._interval,
            "links": links,
            "fault": broken.key if broken else None,
            "push_configured": self.notifier.configured,
        }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def internet_probe(http: httpx.AsyncClient) -> Callable[[], Awaitable[bool]]:
    async def probe() -> bool:
        for url in INTERNET_PROBES:
            try:
                response = await http.get(url, timeout=5)
                if response.status_code < 500:
                    return True
            except httpx.HTTPError:
                continue
        return False

    return probe


def heartbeat_ping(http: httpx.AsyncClient, url: str) -> Callable[[], Awaitable[None]]:
    async def ping() -> None:
        await http.get(url, timeout=10)

    return ping
