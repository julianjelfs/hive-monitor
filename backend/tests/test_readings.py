from datetime import datetime

from app.readings import HOTWATER_SCHEDULE, changes, flatten

from .fixtures import nodes

# Weekday mornings 06:00-07:30, evenings 17:00-18:00, like the house's.
WEEKDAY = [
    {"value": {"status": "ON"}, "start": 360},
    {"value": {"status": "OFF"}, "start": 450},
    {"value": {"status": "ON"}, "start": 1020},
    {"value": {"status": "OFF"}, "start": 1080},
]
SCHEDULE = {day: WEEKDAY for day in ("monday", "tuesday", "wednesday", "thursday", "friday")} | {
    "saturday": [{"value": {"status": "ON"}, "start": 420}, {"value": {"status": "OFF"}, "start": 1320}],
    "sunday": [{"value": {"status": "ON"}, "start": 480}],
}

THURSDAY = datetime(2026, 10, 8)


def says(when: datetime) -> str:
    return flatten(nodes(hotwater_schedule=SCHEDULE), when)[("hotwater", HOTWATER_SCHEDULE)]


def test_every_field_of_the_heating_devices_is_a_reading():
    seen = flatten(nodes(), THURSDAY)
    assert seen[("receiver", "props.online")] == "true"
    assert seen[("hotwater", "state.mode")] == '"SCHEDULE"'
    assert seen[("thermostat", "props.battery")] == "60"
    assert seen[("heating", "props.temperature")] == "19.4"
    assert seen[("hive", "status")] == '"OK"'
    # One day of a schedule is one reading.
    assert ("hotwater", "state.schedule.monday") in flatten(nodes(hotwater_schedule=SCHEDULE), THURSDAY)


def test_invariant_22_fields_that_tick_by_themselves_write_nothing():
    """Invariant 22: lastSeen is never a reading, and the hub's uptime is logged only when it falls."""
    first = flatten(nodes(uptime=1000), THURSDAY)
    assert not any(path == "lastSeen" for _, path in first)
    later = flatten(nodes(uptime=1060), THURSDAY)
    assert changes(first, later) == []
    restarted = flatten(nodes(uptime=30), THURSDAY)
    assert changes(later, restarted) == [("hub", "props.uptime", "1060", "30")]


def test_invariant_24_schedule_says_follows_hives_schedule_in_local_time():
    """Invariant 24: "schedule says" is the slot in force now, carrying over from yesterday."""
    assert says(THURSDAY.replace(hour=5, minute=59)) == "false"
    assert says(THURSDAY.replace(hour=6)) == "true"
    assert says(THURSDAY.replace(hour=7, minute=29)) == "true"
    assert says(THURSDAY.replace(hour=7, minute=30)) == "false"
    # Sunday before 08:00 is still Saturday's last slot, which was off.
    assert says(datetime(2026, 10, 11, 7, 59)) == "false"
    assert says(datetime(2026, 10, 11, 8, 0)) == "true"
    # Monday 01:00 carries Sunday's last slot: on.
    assert says(datetime(2026, 10, 12, 1, 0)) == "true"


def test_no_schedule_means_no_schedule_reading():
    assert ("hotwater", HOTWATER_SCHEDULE) not in flatten(nodes(), THURSDAY)
