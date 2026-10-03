"""Decide when a change in a link's state is real, and when it is worth a notification.

A single bad poll is noise: Hive's API has hiccups that fix themselves. A link only
changes state after it has shown the new state for `confirm_after` polls in a row.

Notifications follow outages, not states. A link that goes down sends one alert. It
sends one recovery when it is next healthy, even if it passed through unknown on the
way (say the hub dropped while the receiver was already down), so every alert gets
its all-clear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .chain import Link, State

HEALTHY = (State.OK, State.WARN)


@dataclass(frozen=True)
class Transition:
    key: str
    label: str
    old: State
    new: State
    at: datetime
    detail: str
    # "down", "recovered" or None. Only these reach the phone.
    alert: str | None
    # For a recovery, when the outage began.
    down_since: datetime | None = None
    # The link's first confirmed state since the monitor started.
    first: bool = False


@dataclass
class _Track:
    state: State
    since: datetime
    detail: str = ""
    pending: State | None = None
    pending_count: int = 0
    # Set when a down alert went out, cleared by the matching recovery.
    alerted_at: datetime | None = None
    confirmed_once: bool = False


@dataclass
class Tracker:
    confirm_after: int = 2
    _tracks: dict[str, _Track] = field(default_factory=dict)

    def update(self, links: list[Link], now: datetime) -> list[Transition]:
        transitions = []
        for link in links:
            track = self._tracks.get(link.key)
            if track is None:
                track = self._tracks[link.key] = _Track(State.UNKNOWN, now, "Not checked yet")

            if link.state == track.state:
                track.pending, track.pending_count = None, 0
                track.detail = link.detail
                continue

            if link.state == track.pending:
                track.pending_count += 1
            else:
                track.pending, track.pending_count = link.state, 1
            if track.pending_count < self.confirm_after:
                continue

            old = track.state
            track.state, track.since, track.detail = link.state, now, link.detail
            track.pending, track.pending_count = None, 0

            alert = None
            down_since = None
            if link.state == State.DOWN and track.alerted_at is None:
                alert = "down"
                track.alerted_at = now
            elif link.state in HEALTHY and track.alerted_at is not None:
                alert = "recovered"
                down_since = track.alerted_at
                track.alerted_at = None

            first = not track.confirmed_once
            track.confirmed_once = True
            transitions.append(
                Transition(link.key, link.label, old, link.state, now, link.detail, alert, down_since, first)
            )
        return transitions

    def since(self, key: str) -> datetime | None:
        track = self._tracks.get(key)
        return track.since if track else None

    def confirmed(self, key: str) -> State:
        track = self._tracks.get(key)
        return track.state if track else State.UNKNOWN
