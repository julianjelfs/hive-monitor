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
