"""One-off login: type in Hive's SMS code so the monitor can log in alone from then on.

Run on the Pi, from backend/:

    .venv/bin/python -m app.setup

Then restart the service. Run it again whenever the status page says Hive wants a code.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from .db import Store
from .hive import register_device

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines, as systemd's EnvironmentFile reads them.

    Read here rather than sourced by the shell, so a password with a $ in it arrives intact.
    """
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def main() -> None:
    env = {**read_env_file(ENV_FILE), **os.environ}
    username = env.get("HIVE_USERNAME")
    password = env.get("HIVE_PASSWORD")
    if not username or not password:
        sys.exit(f"Set HIVE_USERNAME and HIVE_PASSWORD in {ENV_FILE} first.")

    store = Store()

    def ask_code() -> str:
        return input("Hive has texted you a code. Type it here: ").strip()

    asyncio.run(register_device(username, password, store, ask_code))
    print("Done. Hive now remembers this Pi. Restart the monitor: sudo systemctl restart hive")


if __name__ == "__main__":
    main()
