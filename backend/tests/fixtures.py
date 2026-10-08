"""Hive nodes/all responses, shaped like the real thing (from pyhiveapi's sample data)."""

from __future__ import annotations


def nodes(
    hub: bool = True,
    receiver: bool = True,
    thermostat: bool = True,
    battery: int = 60,
    hotwater_mode: str = "SCHEDULE",
    hotwater_online: bool = True,
    hotwater_on: bool = False,
    heating_on: bool = False,
    uptime: int = 1000,
    hotwater_schedule: dict | None = None,
) -> dict:
    hotwater_state = {"name": "Hot Water", "mode": hotwater_mode, "status": "ON" if hotwater_on else "OFF"}
    if hotwater_schedule is not None:
        hotwater_state["schedule"] = hotwater_schedule
    return {
        "status": "OK",
        "devices": [
            {
                "id": "hub-1",
                "type": "hub",
                "lastSeen": 1791445069250 + uptime,
                "props": {"online": hub, "model": "NANO2", "power": "mains", "signal": 100, "uptime": uptime},
                "state": {"name": "Hub"},
            },
            {
                "id": "slr-1",
                "type": "boilermodule",
                "parent": "hub-1",
                "props": {"online": receiver, "model": "SLR2", "power": "mains", "signal": 88},
                "state": {"name": "Receiver"},
            },
            {
                "id": "slt-1",
                "type": "thermostatui",
                "parent": "hub-1",
                "props": {
                    "online": thermostat,
                    "model": "SLT3",
                    "power": "battery",
                    "battery": battery,
                    "signal": 72,
                },
                "state": {"name": "Hall thermostat"},
            },
        ],
        "products": [
            {
                "id": "slr-1",
                "type": "hotwater",
                "props": {"online": hotwater_online, "working": hotwater_on},
                "state": hotwater_state,
            },
            {
                "id": "slr-1",
                "type": "heating",
                "props": {"online": True, "temperature": 19.4, "working": heating_on},
                "state": {"name": "Heating", "mode": "SCHEDULE", "target": 20},
            },
        ],
    }
