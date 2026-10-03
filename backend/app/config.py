"""Settings from the environment. On the Pi they come from backend/.env via systemd."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    hive_username: str
    hive_password: str
    ntfy_topic: str | None
    ntfy_server: str
    public_url: str
    heartbeat_url: str | None
    interval: float
    confirm_after: int
    poll: bool


def load() -> Settings:
    env = os.environ.get
    return Settings(
        hive_username=env("HIVE_USERNAME", ""),
        hive_password=env("HIVE_PASSWORD", ""),
        ntfy_topic=env("NTFY_TOPIC") or None,
        ntfy_server=env("NTFY_SERVER", "https://ntfy.sh"),
        public_url=env("PUBLIC_URL", "https://hive.julianjelfs.co.uk"),
        heartbeat_url=env("HEARTBEAT_URL") or None,
        interval=float(env("POLL_SECONDS", "60")),
        confirm_after=int(env("CONFIRM_AFTER", "2")),
        # Off for tests and for working on the UI without hitting Hive.
        poll=env("HIVE_POLL", "1") != "0",
    )
