from app.chain import Observation, State, assess

from .fixtures import nodes


def states(obs: Observation) -> dict[str, State]:
    return {link.key: link.state for link in assess(obs)}


def test_everything_online_is_all_ok():
    assert set(states(Observation(nodes=nodes())).values()) == {State.OK}


def test_invariant_4_only_the_first_broken_link_is_down():
    """Invariant 4: only the first broken link in the chain is down; links behind it are unknown."""
    result = states(Observation(nodes=nodes(hub=False, receiver=False, thermostat=False)))
    assert result["hub"] == State.DOWN
    assert result["receiver"] == State.UNKNOWN
    assert result["thermostat"] == State.UNKNOWN
    assert result["hotwater"] == State.UNKNOWN
    assert result["heating"] == State.UNKNOWN


def test_invariant_4_receiver_down_leaves_thermostat_alone():
    """Invariant 4: the thermostat hangs off the hub, not the receiver, so it still reports."""
    result = states(Observation(nodes=nodes(receiver=False)))
    assert result["receiver"] == State.DOWN
    assert result["thermostat"] == State.OK
    assert result["hotwater"] == State.UNKNOWN


def test_invariant_5_no_internet_blames_the_internet_not_hive():
    """Invariant 5: when the Pi loses the internet, that link is down and Hive is unknown."""
    result = states(Observation(nodes=None, hive_error="timeout", internet=False))
    assert result["internet"] == State.DOWN
    assert result["hive"] == State.UNKNOWN
    assert result["hub"] == State.UNKNOWN


def test_hive_failing_with_internet_up_is_hive_down():
    links = {l.key: l for l in assess(Observation(nodes=None, hive_error="Hive answered 503"))}
    assert links["internet"].state == State.OK
    assert links["hive"].state == State.DOWN
    assert links["hive"].detail == "Hive answered 503"


def test_invariant_11_hot_water_switched_off_is_a_warning():
    """Invariant 11: hot water switched off shows as a warning."""
    assert states(Observation(nodes=nodes(hotwater_mode="OFF")))["hotwater"] == State.WARN


def test_invariant_12_low_thermostat_battery_is_a_warning():
    """Invariant 12: a wall thermostat battery under 20% shows as a warning."""
    assert states(Observation(nodes=nodes(battery=19)))["thermostat"] == State.WARN
    assert states(Observation(nodes=nodes(battery=20)))["thermostat"] == State.OK


def test_missing_device_is_down():
    data = nodes()
    data["devices"] = [d for d in data["devices"] if d["type"] != "boilermodule"]
    assert states(Observation(nodes=data))["receiver"] == State.DOWN


def test_offline_detail_names_the_device():
    links = {l.key: l for l in assess(Observation(nodes=nodes(thermostat=False)))}
    assert links["thermostat"].detail == "Offline: Hall thermostat"


def test_heating_detail_keeps_the_degree_sign_capital():
    links = {l.key: l for l in assess(Observation(nodes=nodes()))}
    assert links["heating"].detail == "19.4°C in the house, target 20.0°C, on schedule"


def test_invariant_16_hot_water_and_heating_are_on_exactly_when_hive_says_so():
    """Invariant 16: hot water is on when Hive says it's heating water, heating when the boiler fires."""
    def active(**kw):
        return {l.key: l.active for l in assess(Observation(nodes=nodes(**kw)))}

    assert active()["hotwater"] is False
    assert active(hotwater_on=True)["hotwater"] is True
    assert active()["heating"] is False
    assert active(heating_on=True)["heating"] is True
    # Links with no on/off of their own never claim one.
    assert {k for k, v in active(hotwater_on=True, heating_on=True).items() if v is not None} == {
        "hotwater",
        "heating",
    }


def test_invariant_16_a_link_we_cant_see_is_neither_on_nor_off():
    """Invariant 16: behind a dead link, on/off is unknown, not off."""
    links = {l.key: l for l in assess(Observation(nodes=nodes(receiver=False, hotwater_on=True)))}
    assert links["hotwater"].active is None
    assert links["heating"].active is None
