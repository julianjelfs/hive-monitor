from fastapi.testclient import TestClient


def test_health_and_status(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_DB_PATH", str(tmp_path / "hive.db"))
    monkeypatch.setenv("HIVE_POLL", "0")
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        status = client.get("/api/status").json()
        assert status["links"] == []
        assert status["events"] == []
        assert client.post("/api/check").status_code == 200
        assert client.get("/api/links/hotwater/history").json() == {
            "key": "hotwater",
            "label": "Hot water",
            "entries": [],
        }
        assert client.get("/api/links/nonsense/history").status_code == 404


def test_invariant_19_a_link_history_is_its_own_changes_newest_first(tmp_path):
    """Invariant 19: a link's history holds its state and on/off changes, newest first, and no other link's."""
    from datetime import datetime, timedelta, timezone

    from app.chain import State
    from app.db import Store
    from app.tracker import Transition

    t0 = datetime(2026, 10, 8, 6, 0, tzinfo=timezone.utc)
    at = lambda m: t0 + timedelta(minutes=m)  # noqa: E731
    store = Store(tmp_path / "hive.db")
    store.record_activity("hotwater", at(0), True)
    store.record(Transition("hotwater", "Hot water", State.OK, State.UNKNOWN, at(10), "Can't see", None))
    store.record(Transition("hub", "Hub", State.OK, State.DOWN, at(10), "Offline", "down"))
    store.record_activity("heating", at(15), True)
    store.record(Transition("hotwater", "Hot water", State.UNKNOWN, State.OK, at(20), "On schedule", None))
    store.record_activity("hotwater", at(20), False)

    entries = store.history("hotwater")
    assert [(e["at"], e["kind"]) for e in entries] == [
        (at(20).isoformat(), "activity"),
        (at(20).isoformat(), "state"),
        (at(10).isoformat(), "state"),
        (at(0).isoformat(), "activity"),
    ]
    assert entries[0]["active"] is False
    assert entries[1]["new_state"] == "ok"
    store.close()


def test_only_fingerprinted_assets_are_cached_forever(tmp_path):
    from fastapi import FastAPI

    from app.main import UiFiles

    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("x")
    (tmp_path / "manifest.webmanifest").write_text("{}")
    (tmp_path / "sw.js").write_text("x")
    (tmp_path / "index.html").write_text("<html></html>")
    ui = FastAPI()
    ui.mount("/", UiFiles(directory=tmp_path, html=True))

    with TestClient(ui) as client:
        assert "immutable" in client.get("/assets/index-abc123.js").headers["cache-control"]
        manifest = client.get("/manifest.webmanifest")
        assert manifest.headers["cache-control"] == "no-cache"
        assert manifest.headers["content-type"].startswith("application/manifest+json")
        assert client.get("/sw.js").headers["cache-control"] == "no-cache"
        assert client.get("/").headers["cache-control"] == "no-cache"
