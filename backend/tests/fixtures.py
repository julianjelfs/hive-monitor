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
) -> dict:
    return {
        "devices": [
            {
                "id": "hub-1",
                "type": "hub",
                "props": {"online": hub, "model": "NANO2", "power": "mains", "signal": 100},
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
                "state": {"name": "Hot Water", "mode": hotwater_mode, "status": "ON" if hotwater_on else "OFF"},
            },
            {
                "id": "slr-1",
                "type": "heating",
                "props": {"online": True, "temperature": 19.4, "working": heating_on},
                "state": {"name": "Heating", "mode": "SCHEDULE", "target": 20},
            },
        ],
    }
