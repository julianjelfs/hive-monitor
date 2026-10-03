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
