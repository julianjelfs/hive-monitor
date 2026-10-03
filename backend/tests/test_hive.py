import httpx
import pytest

from app import hive
from app.db import Store
from app.hive import DEVICE_KEY, HiveClient, HiveNeedsSetup

from .fixtures import nodes

TOKENS = {"AuthenticationResult": {"IdToken": "id-1", "RefreshToken": "r-1", "ExpiresIn": 3600}}


class FakeAuth:
    """Stands in for pyhive's Cognito client. `script` decides what login returns."""

    DEVICE_VERIFIER_CHALLENGE = "DEVICE_SRP_AUTH"
    SMS_MFA_CHALLENGE = "SMS_MFA"
    instances: list["FakeAuth"] = []
    script = "device"

    def __init__(self, username, password, device_group_key=None, device_key=None, device_password=None):
        self.device = (device_group_key, device_key, device_password)
        self.device_logins = 0
        FakeAuth.instances.append(self)

    async def login(self):
        if FakeAuth.script == "sms":
            return {"ChallengeName": "SMS_MFA", "Session": "s"}
        return {"ChallengeName": "DEVICE_SRP_AUTH"}

    async def device_login(self):
        self.device_logins += 1
        return TOKENS

    async def refresh_token(self, token):
        return TOKENS


@pytest.fixture(autouse=True)
def fake_auth(monkeypatch):
    FakeAuth.instances = []
    FakeAuth.script = "device"
    monkeypatch.setattr(hive, "HiveAuthAsync", FakeAuth)


@pytest.fixture
def requests_seen():
    return []


@pytest.fixture
async def http(requests_seen):
    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        return httpx.Response(200, json=nodes())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        yield client


def remember_device(path):
    store = Store(path)
    store.put_json(DEVICE_KEY, {"group_key": "g", "key": "k", "password": "p"})
    store.close()


async def test_invariant_9_device_keys_survive_a_restart(tmp_path, http):
    """Invariant 9: device keys live in the database, and a fresh process logs in with them, no SMS."""
    remember_device(tmp_path / "hive.db")

    store = Store(tmp_path / "hive.db")  # a new process opening the same file
    result = await HiveClient("me@example.com", "pw", store, http).fetch()

    assert result["devices"]
    auth = FakeAuth.instances[0]
    assert auth.device == ("g", "k", "p")
    assert auth.device_logins == 1


async def test_invariant_8_the_monitor_only_reads_from_hive(tmp_path, http, requests_seen):
    """Invariant 8: every request the monitor makes to Hive is a GET."""
    remember_device(tmp_path / "hive.db")
    client = HiveClient("me@example.com", "pw", Store(tmp_path / "hive.db"), http)
    for _ in range(3):
        await client.fetch()
    assert requests_seen
    assert {r.method for r in requests_seen} == {"GET"}
    assert all(r.url.host == "beekeeper.hivehome.com" for r in requests_seen)


async def test_token_is_reused_between_polls(tmp_path, http):
    remember_device(tmp_path / "hive.db")
    client = HiveClient("me@example.com", "pw", Store(tmp_path / "hive.db"), http)
    await client.fetch()
    await client.fetch()
    assert FakeAuth.instances[0].device_logins == 1


async def test_sms_challenge_means_setup_needed(tmp_path, http):
    remember_device(tmp_path / "hive.db")
    FakeAuth.script = "sms"
    with pytest.raises(HiveNeedsSetup):
        await HiveClient("me@example.com", "pw", Store(tmp_path / "hive.db"), http).fetch()


async def test_no_device_keys_means_setup_needed(tmp_path, http):
    with pytest.raises(HiveNeedsSetup):
        await HiveClient("me@example.com", "pw", Store(tmp_path / "hive.db"), http).fetch()
