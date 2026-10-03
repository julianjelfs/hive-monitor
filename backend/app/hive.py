"""Read-only access to Hive's cloud API.

Hive has no public API. This uses the private one behind the Hive app, through the same
login library Home Assistant uses (pyhive-integration). Hive logs in with AWS Cognito and
an SMS code. The SMS step happens once, in `python -m app.setup`, which registers this Pi
as a remembered device and stores its keys. After that the monitor logs in with the
device keys and never needs a code, until Hive forgets the device.

The monitor only ever reads. Nothing here sends a command to the heating.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from apyhiveapi.api.hive_auth_async import HiveAuthAsync

from .db import Store

log = logging.getLogger(__name__)

NODES_URL = "https://beekeeper.hivehome.com/1.0/nodes/all?products=true&devices=true&actions=true"
# The library sends the app's user agent; do the same so these requests look like the app's.
USER_AGENT = "Hive/12.04.0 iOS/18.3.1 Apple"
DEVICE_KEY = "hive_device"
# Refresh when 90% of the token's life has gone, so a poll never carries a dead token.
REFRESH_AT = 0.9


class HiveNeedsSetup(Exception):
    """Login needs a person: run setup again and type in the SMS code."""


class HiveClient:
    def __init__(self, username: str, password: str, store: Store, http: httpx.AsyncClient):
        self._username = username
        self._password = password
        self._store = store
        self._http = http
        self._auth: HiveAuthAsync | None = None
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at = 0.0

    async def fetch(self) -> dict[str, Any]:
        token = await self._token()
        response = await self._get(token)
        if response.status_code == 401:
            # Hive dropped the token early. Log in again once before calling it a failure.
            self._id_token = None
            response = await self._get(await self._token())
        response.raise_for_status()
        return response.json()

    async def _get(self, token: str) -> httpx.Response:
        return await self._http.get(
            NODES_URL,
            headers={"Authorization": token, "Accept": "*/*", "User-Agent": USER_AGENT},
            timeout=20,
        )

    async def _token(self) -> str:
        if self._id_token and time.time() < self._expires_at:
            return self._id_token
        if self._refresh_token:
            try:
                result = await self._get_auth().refresh_token(self._refresh_token)
                self._keep(result)
                return self._id_token  # type: ignore[return-value]
            except Exception as err:  # noqa: BLE001 - any refresh failure means log in again
                log.info("token refresh failed (%s), logging in again", type(err).__name__)
                self._refresh_token = None
        result = await self._login()
        self._keep(result)
        return self._id_token  # type: ignore[return-value]

    async def _login(self) -> dict:
        device = self._store.get_json(DEVICE_KEY)
        if not device:
            raise HiveNeedsSetup("Not set up yet. Run setup on the Pi.")
        auth = self._get_auth(device)
        result = await auth.login()
        if result and "AuthenticationResult" in result:
            return result
        challenge = (result or {}).get("ChallengeName")
        if challenge == auth.DEVICE_VERIFIER_CHALLENGE:
            result = await auth.device_login()
            if result and "AuthenticationResult" in result:
                return result
            challenge = (result or {}).get("ChallengeName")
        if challenge == auth.SMS_MFA_CHALLENGE:
            raise HiveNeedsSetup("Hive forgot this Pi and wants an SMS code. Run setup on the Pi.")
        raise RuntimeError(f"Hive login stopped at an unexpected step: {challenge}")

    def _get_auth(self, device: dict | None = None) -> HiveAuthAsync:
        if self._auth is None:
            device = device or self._store.get_json(DEVICE_KEY) or {}
            self._auth = HiveAuthAsync(
                self._username,
                self._password,
                device_group_key=device.get("group_key"),
                device_key=device.get("key"),
                device_password=device.get("password"),
            )
        return self._auth

    def _keep(self, result: dict) -> None:
        tokens = result["AuthenticationResult"]
        self._id_token = tokens["IdToken"]
        # A refresh doesn't hand back a new refresh token; keep the one we have.
        self._refresh_token = tokens.get("RefreshToken", self._refresh_token)
        self._expires_at = time.time() + tokens.get("ExpiresIn", 3600) * REFRESH_AT


async def register_device(username: str, password: str, store: Store, ask_code) -> None:
    """Log in with an SMS code and remember this Pi, so later logins need no code.

    ask_code is a callable returning the code the person typed in.
    """
    auth = HiveAuthAsync(username, password)
    result = await auth.login()
    if result and result.get("ChallengeName") == auth.SMS_MFA_CHALLENGE:
        result = await auth.sms_2fa(ask_code(), result)
    if not result or "AuthenticationResult" not in result:
        raise RuntimeError(f"Hive login did not finish: {result and result.get('ChallengeName')}")
    if not auth.device_key:
        raise RuntimeError("Hive did not offer to remember this device, so setup can't finish.")
    await auth.device_registration("hive-monitor")
    group_key, key, device_password = await auth.get_device_data()
    store.put_json(DEVICE_KEY, {"group_key": group_key, "key": key, "password": device_password})
