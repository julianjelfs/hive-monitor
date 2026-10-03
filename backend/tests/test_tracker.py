from datetime import datetime, timedelta, timezone

from app.chain import Link, State
from app.tracker import Tracker

T0 = datetime(2026, 10, 3, 7, 0, tzinfo=timezone.utc)


def link(state: State, key: str = "receiver") -> list[Link]:
    return [Link(key, "Hub to boiler receiver", state, "detail")]


def feed(tracker: Tracker, *states: State, start: int = 0):
    """One poll per state, a minute apart. Returns every transition in order."""
    out = []
    for i, state in enumerate(states):
        out += tracker.update(link(state), T0 + timedelta(minutes=start + i))
    return out


def alerts(transitions):
    return [t.alert for t in transitions if t.alert]


def test_invariant_1_one_bad_poll_sends_nothing():
    """Invariant 1: a link alerts only after confirm_after consecutive bad polls."""
    tracker = Tracker(confirm_after=2)
    assert alerts(feed(tracker, State.OK, State.OK, State.DOWN, State.OK, State.OK)) == []


def test_invariant_1_two_bad_polls_alert():
    """Invariant 1: the second bad poll in a row confirms the outage."""
    tracker = Tracker(confirm_after=2)
    assert alerts(feed(tracker, State.OK, State.OK, State.DOWN, State.DOWN)) == ["down"]


def test_invariant_2_a_long_outage_sends_one_alert():
    """Invariant 2: an outage sends exactly one down alert, however long it lasts."""
    tracker = Tracker(confirm_after=2)
    assert alerts(feed(tracker, State.OK, State.OK, *[State.DOWN] * 50)) == ["down"]


def test_invariant_3_recovery_names_the_outage_length():
    """Invariant 3: every down alert gets one recovery, carrying when the outage began."""
    tracker = Tracker(confirm_after=2)
    transitions = feed(tracker, State.OK, State.OK, State.DOWN, State.DOWN, State.DOWN, State.OK, State.OK)
    assert alerts(transitions) == ["down", "recovered"]
    recovery = transitions[-1]
    assert recovery.down_since == T0 + timedelta(minutes=3)
    assert recovery.at == T0 + timedelta(minutes=6)


def test_invariant_3_recovery_survives_a_trip_through_unknown():
    """Invariant 3: a down link hidden behind a later upstream fault still gets its recovery."""
    tracker = Tracker(confirm_after=1)
    transitions = feed(tracker, State.OK, State.DOWN, State.UNKNOWN, State.UNKNOWN, State.OK)
    assert alerts(transitions) == ["down", "recovered"]


def test_invariant_2_down_unknown_down_does_not_alert_twice():
    """Invariant 2: going down, unknown, then down again is still one outage."""
    tracker = Tracker(confirm_after=1)
    assert alerts(feed(tracker, State.OK, State.DOWN, State.UNKNOWN, State.DOWN)) == ["down"]


def test_unknown_never_alerts():
    tracker = Tracker(confirm_after=1)
    assert alerts(feed(tracker, State.OK, State.UNKNOWN, State.OK)) == []


def test_warning_counts_as_recovered():
    tracker = Tracker(confirm_after=1)
    assert alerts(feed(tracker, State.DOWN, State.WARN)) == ["down", "recovered"]


def test_broken_from_the_first_poll_still_alerts():
    tracker = Tracker(confirm_after=2)
    assert alerts(feed(tracker, State.DOWN, State.DOWN)) == ["down"]
