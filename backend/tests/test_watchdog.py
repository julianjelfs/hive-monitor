from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.chain import Observation, State, assess
from app.watchdog import Watchdog

from .fixtures import nodes
from .test_readings import SCHEDULE

LONDON = ZoneInfo("Europe/London")
# Thursday 15 October 2026, 06:00 in the house: the morning hot water slot starts.
SIX_AM = datetime(2026, 10, 15, 5, 0, tzinfo=timezone.utc)


def run(watchdog, polls):
    """Feed (minutes after 06:00, nodes) to the watchdog; the links after each poll."""
    out = []
    for minutes, body in polls:
        out.append({l.key: l for l in watchdog.check(assess(Observation(body)), body, SIX_AM + timedelta(minutes=minutes))})
    return out


def hotwater(**kw):
    return nodes(hotwater_schedule=SCHEDULE, **kw)


def test_invariant_27_a_missed_schedule_run_is_down_until_the_boiler_heats_water():
    """Invariant 27: hot water that should be on but hasn't started within 5 minutes is down, and stays
    down after the slot ends, until the boiler is seen heating water."""
    seen = run(
        Watchdog(LONDON),
        [(0, hotwater()), (4, hotwater()), (5, hotwater()), (120, hotwater()), (121, hotwater(hotwater_on=True))],
    )
    states = [s["hotwater"].state for s in seen]
    assert states == [State.OK, State.OK, State.DOWN, State.DOWN, State.OK]
    assert "Schedule said on at Thu 06:00" in seen[2]["hotwater"].detail


def test_invariant_27_a_boost_the_boiler_ignores_is_down():
    """Invariant 27: Hive showing a boost while the boiler never starts heating water is down."""
    boost = hotwater(hotwater_mode="BOOST", hotwater_on=False)
    boost["products"][0]["state"]["status"] = "ON"
    seen = run(Watchdog(LONDON), [(80, boost), (85, boost)])
    assert seen[1]["hotwater"].state == State.DOWN
    assert "Boost started at Thu 07:20" in seen[1]["hotwater"].detail


def test_invariant_27_a_run_that_starts_is_never_down():
    """Invariant 27: on a good morning the boiler starts with the schedule and nothing alerts."""
    seen = run(Watchdog(LONDON), [(m, hotwater(hotwater_on=True)) for m in range(0, 90, 5)] + [(95, hotwater())])
    assert all(s["hotwater"].state == State.OK for s in seen)


def test_invariant_28_a_frozen_house_temperature_puts_the_thermostat_down():
    """Invariant 28: a house temperature unchanged for 2 hours puts the thermostat down until it changes."""
    seen = run(
        Watchdog(LONDON),
        [(0, nodes(temperature=19.0)), (119, nodes(temperature=19.0)), (120, nodes(temperature=19.0)), (121, nodes(temperature=19.1))],
    )
    assert [s["thermostat"].state for s in seen] == [State.OK, State.OK, State.DOWN, State.OK]
    assert "19.0°C since Thu 06:00" in seen[2]["thermostat"].detail


def test_a_failed_poll_checks_nothing():
    links = assess(Observation(None, "timeout"))
    assert Watchdog(LONDON).check(links, None, SIX_AM) == links
