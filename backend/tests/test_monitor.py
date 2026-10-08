import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.chain import State
from app.db import Store
from app.hive import HiveNeedsSetup
from app.monitor import Monitor

from .fixtures import nodes

T0 = datetime(2026, 10, 3, 7, 0, tzinfo=timezone.utc)


class Source:
    """Hands out one scripted result per poll: a dict, or an exception to raise."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = 0

    async def fetch(self):
        self.calls += 1
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return result


class Phone:
    def __init__(self, fail: bool = False):
        self.sent: list[tuple[str, str, bool]] = []
        self.fail = fail

    configured = True

    async def send(self, title, body, urgent):
        if self.fail:
            raise ConnectionError("ntfy unreachable")
        self.sent.append((title, body, urgent))


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        self.now += timedelta(minutes=1)
        return self.now


async def online():
    return True


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "hive.db")
    yield s
    s.close()


def make(source, store, phone=None, internet=online, confirm_after=2):
    return Monitor(
        source=source,
        store=store,
        notifier=phone or Phone(),
        internet=internet,
        confirm_after=confirm_after,
        clock=Clock(),
    )


async def polls(monitor, n):
    for _ in range(n):
        await monitor.poll_once()


async def test_receiver_dropping_sends_one_alert_naming_it(store):
    phone = Phone()
    monitor = make(Source(nodes(), nodes(), nodes(receiver=False)), store, phone)
    await polls(monitor, 6)
    assert [title for title, _, _ in phone.sent] == ["Hive: Hub to boiler receiver is down"]


async def test_invariant_6_lost_login_alerts_rather_than_going_quiet(store):
    """Invariant 6: Hive wanting an SMS code shows as Hive cloud down, and alerts."""
    phone = Phone()
    needs_code = HiveNeedsSetup("Hive forgot this Pi and wants an SMS code. Run setup on the Pi.")
    monitor = make(Source(nodes(), nodes(), needs_code), store, phone)
    await polls(monitor, 4)
    links = {l.key: l for l in monitor.links}
    assert links["hive"].state == State.DOWN
    assert "SMS code" in links["hive"].detail
    assert phone.sent[0][0] == "Hive: Hive cloud is down"


async def test_invariant_7_a_failed_push_does_not_stop_polling(store):
    """Invariant 7: a push that fails is logged and the monitor carries on."""
    monitor = make(Source(nodes(receiver=False)), store, Phone(fail=True))
    await polls(monitor, 4)
    assert monitor.checked_at == T0 + timedelta(minutes=4)


async def test_invariant_7_a_crash_inside_a_poll_does_not_stop_the_loop(store):
    """Invariant 7: an exception escaping poll_once is caught by run(), which keeps going."""
    calls = 0

    async def flaky_internet():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        return True

    source = Source(RuntimeError("hive down"))
    monitor = Monitor(source, store, Phone(), flaky_internet, interval=0.01, clock=Clock())
    task = asyncio.create_task(monitor.run())
    await asyncio.sleep(0.2)
    task.cancel()
    assert source.calls >= 3


async def test_invariant_10_every_confirmed_change_is_logged(store):
    """Invariant 10: every confirmed state change is logged, except a link starting up healthy."""
    monitor = make(Source(nodes(), nodes(), nodes(hub=False), nodes(hub=False), nodes()), store)
    await polls(monitor, 6)
    hub_events = [(e["old_state"], e["new_state"]) for e in reversed(store.recent_events()) if e["link"] == "hub"]
    assert hub_events == [("ok", "down"), ("down", "ok")]


async def test_invariant_10_a_link_broken_at_startup_is_logged(store):
    """Invariant 10: a link that is already down when the monitor starts still gets a log row."""
    monitor = make(Source(nodes(hub=False)), store)
    await polls(monitor, 2)
    assert [(e["link"], e["new_state"]) for e in store.recent_events() if e["new_state"] == "down"] == [
        ("hub", "down")
    ]


async def test_no_internet_alerts_about_the_internet_only(store):
    async def offline():
        return False

    phone = Phone()
    monitor = make(Source(OSError("no route")), store, phone, internet=offline)
    await polls(monitor, 3)
    assert [title for title, _, _ in phone.sent] == ["Hive: Pi to internet is down"]


async def test_snapshot_names_the_first_fault(store):
    monitor = make(Source(nodes(hub=False)), store)
    await polls(monitor, 2)
    snap = monitor.snapshot()
    assert snap["fault"] == "hub"
    assert [l["state"] for l in snap["links"]] == ["ok", "ok", "down", "unknown", "unknown", "unknown", "unknown"]


def activity(store, key):
    return [e["active"] for e in reversed(store.history(key)) if e["kind"] == "activity"]


async def test_invariant_17_each_on_off_change_is_logged_once(store):
    """Invariant 17: each on/off change writes one row; polls that see no change write nothing."""
    off, on = nodes(), nodes(hotwater_on=True)
    monitor = make(Source(off, off, on, on, on, off, off), store)
    await polls(monitor, 7)
    assert activity(store, "hotwater") == [False, True, False]
    assert activity(store, "heating") == [False]


async def test_invariant_17_a_restart_does_not_log_the_same_on_off_again(store):
    """Invariant 17: after a restart, an unchanged on/off writes nothing."""
    await polls(make(Source(nodes(hotwater_on=True)), store), 2)
    await polls(make(Source(nodes(hotwater_on=True)), store), 2)
    assert activity(store, "hotwater") == [True]


async def test_invariant_18_losing_sight_of_hot_water_does_not_log_it_off(store):
    """Invariant 18: a link we can't see writes no on/off, so a gap never reads as "off"."""
    on = nodes(hotwater_on=True)
    monitor = make(Source(on, nodes(receiver=False), nodes(receiver=False), OSError("blip"), on), store)
    await polls(monitor, 5)
    assert activity(store, "hotwater") == [True]


def readings(store, link=None):
    return [(r["link"], r["path"], r["old"], r["new"]) for r in reversed(store.readings()) if link in (None, r["link"])]


async def test_invariant_21_each_field_change_is_logged_once(store):
    """Invariant 21: a change in any field Hive reports writes one row; no change, or a restart, writes nothing."""
    monitor = make(Source(nodes(), nodes(), nodes(hotwater_mode="BOOST"), nodes(hotwater_mode="BOOST")), store)
    await polls(monitor, 4)
    baseline = len(store.readings())
    await polls(make(Source(nodes(hotwater_mode="BOOST")), store), 2)
    assert len(store.readings()) == baseline
    mode = [(old, new) for link, path, old, new in readings(store, "hotwater") if path == "state.mode"]
    assert mode == [(None, '"SCHEDULE"'), ('"SCHEDULE"', '"BOOST"')]


async def test_invariant_23_a_single_failed_poll_is_logged_and_devices_keep_their_values(store):
    """Invariant 23: one failed poll logs why, though no link changes state, and logs no device as gone."""
    monitor = make(Source(nodes(), OSError("blip"), nodes()), store)
    await polls(monitor, 3)
    assert [new for link, path, old, new in readings(store, "hive") if path == "poll"] == [
        '"ok"',
        '"Couldn\'t reach Hive (OSError)"',
        '"ok"',
    ]
    assert [path for link, path, *_ in readings(store, "receiver") if path == "props.online"] == ["props.online"]
    assert all(e["new_state"] != "down" for e in store.recent_events())
