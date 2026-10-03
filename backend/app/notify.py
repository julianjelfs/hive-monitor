"""Push notifications through ntfy.

ntfy.sh relays a POST to every phone subscribed to the topic, in the free ntfy app.
Anyone who knows the topic name can read it, so the name is long and random and lives
in the .env, not the repo.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from .tracker import Transition

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, http: httpx.AsyncClient, topic: str | None, server: str, click_url: str):
        self._http = http
        self._topic = topic
        self._server = server.rstrip("/")
        self._click_url = click_url

    @property
    def configured(self) -> bool:
        return bool(self._topic)

    async def send(self, title: str, message: str, urgent: bool) -> None:
        if not self._topic:
            log.warning("no NTFY_TOPIC set, not sending: %s", title)
            return
        response = await self._http.post(
            f"{self._server}/{self._topic}",
            content=message.encode(),
            headers={
                "Title": title,
                # 5 is ntfy's max: long vibration and a pop-over on Android.
                "Priority": "5" if urgent else "3",
                "Tags": "rotating_light" if urgent else "white_check_mark",
                "Click": self._click_url,
            },
            timeout=10,
        )
        response.raise_for_status()


def message_for(t: Transition) -> tuple[str, str, bool]:
    """Title, body and urgency for a transition that alerts."""
    if t.alert == "down":
        return f"Hive: {t.label} is down", t.detail, True
    outage = _duration(t.down_since, t.at) if t.down_since else "a while"
    return f"Hive: {t.label} is back", f"Down for {outage}. {t.detail}", False


def _duration(start: datetime, end: datetime) -> str:
    minutes = max(1, round((end - start).total_seconds() / 60))
    if minutes < 60:
        return f"{minutes} min"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} min" if minutes else f"{hours} h"
