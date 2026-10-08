"""Hive monitor: one process that polls Hive, sends alerts and serves the status page."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from . import config
from .chain import LABELS
from .db import Store
from .hive import HiveClient
from .monitor import Monitor, heartbeat_ping, internet_probe
from .notify import Notifier

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Python's table doesn't know the manifest; browsers want this type for it.
mimetypes.add_type("application/manifest+json", ".webmanifest")

DEFAULT_UI_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def build_monitor(settings: config.Settings, store: Store, http: httpx.AsyncClient) -> Monitor:
    return Monitor(
        source=HiveClient(settings.hive_username, settings.hive_password, store, http),
        store=store,
        notifier=Notifier(http, settings.ntfy_topic, settings.ntfy_server, settings.public_url),
        internet=internet_probe(http),
        heartbeat=heartbeat_ping(http, settings.heartbeat_url) if settings.heartbeat_url else None,
        interval=settings.interval,
        confirm_after=settings.confirm_after,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = config.load()
    store = Store()
    async with httpx.AsyncClient() as http:
        monitor = build_monitor(settings, store, http)
        app.state.store, app.state.monitor = store, monitor
        task = asyncio.create_task(monitor.run()) if settings.poll else None
        try:
            yield
        finally:
            if task:
                task.cancel()
            store.close()


app = FastAPI(title="Hive monitor", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def status(request: Request) -> dict:
    snapshot = request.app.state.monitor.snapshot()
    snapshot["events"] = request.app.state.store.recent_events(30)
    return snapshot


@app.get("/api/links/{key}/history")
def history(key: str, request: Request) -> dict:
    if key not in LABELS:
        raise HTTPException(404, f"No link called {key!r}")
    return {"key": key, "label": LABELS[key], "entries": request.app.state.store.history(key)}


@app.post("/api/check")
def check_now(request: Request) -> dict[str, str]:
    request.app.state.monitor.check_now()
    return {"status": "checking"}


@app.post("/api/test-push")
async def test_push(request: Request) -> dict[str, str]:
    notifier = request.app.state.monitor.notifier
    if not notifier.configured:
        raise HTTPException(409, "NTFY_TOPIC is not set on the Pi")
    await notifier.send("Hive monitor test", "If you can read this, alerts will reach you.", urgent=True)
    return {"status": "sent"}


def ui_directory() -> Path:
    override = os.environ.get("HIVE_UI_DIR")
    return Path(override) if override else DEFAULT_UI_DIR


class UiFiles(StaticFiles):
    """Vite fingerprints what it puts in assets/, so those cache forever.

    Everything else keeps its name across builds (index.html, the manifest, the icons, the
    service worker) and must be revalidated, or a phone holds the old one indefinitely.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        path = Path(str(args[0])) if args else Path()
        if "assets" in path.parts:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response


# Mounted last so the /api routes win. Missing in an unbuilt checkout; use the Vite dev server.
_ui = ui_directory()
if _ui.is_dir():
    app.mount("/", UiFiles(directory=_ui, html=True), name="ui")
