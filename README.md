# Hive monitor

Watches the Hive heating system and sends a push notification when a link in it drops,
so a broken system shows up on the phone instead of in a cold shower.

It runs on the Pi and polls Hive's cloud API every minute. It never sends commands to the
heating, it only reads. The status page at https://hive.julianjelfs.co.uk shows each link
in the chain:

```
Pi → internet → Hive cloud → hub → boiler receiver → hot water, heating
                                 ↘ wall thermostat
```

The first red link is the fault. Links behind it show as unknown, because Hive's picture of
anything behind a dead link is stale. Only the first broken link sends an alert.

## Alerts

Alerts go through [ntfy](https://ntfy.sh). Install the ntfy app, subscribe to the topic
named in the Pi's `backend/.env`, and press "Send test alert" on the status page to check.

- A link alerts after two bad polls in a row, so about two minutes after it breaks.
- One alert per outage, and one "back" message when it recovers, with how long it was down.
- Warnings (hot water switched off, thermostat battery under 20%) show on the page but
  don't notify.

If the broadband goes down the Pi can't send anything. Set `HEARTBEAT_URL` to a
[healthchecks.io](https://healthchecks.io) check and it will alert you when the Pi goes quiet.

## Hive login

Hive has no public API. This uses the private one the app uses, through the library Home
Assistant uses (`pyhive-integration`, pinned). Hive could change it without warning.

Login needs an SMS code once. `scripts/hive setup` logs in, asks for the code, and registers
the Pi as a remembered device. The device keys live in `backend/hive.db`. If Hive ever
forgets the Pi, the "Hive cloud" link goes red with a message saying so: run setup again.

## Where it runs

On the Pi (`julian_jelfs@pi.local`), in `~/hive-monitor`, as the `hive` systemd service on
127.0.0.1:8030. Caddy serves it as hive.julianjelfs.co.uk (the block lives in the
recipe-for-disaster repo). Away from home it's at https://pi.tail50bfbf.ts.net:8449.

It installs as an app (Add to Home Screen on iPhone, Install on Android). Install it from
hive.julianjelfs.co.uk, not the tailnet address: an installed app belongs to one address, so
installing from both gives two apps.

Icons come from `frontend/scripts/icons.mjs`; run `node scripts/icons.mjs` in `frontend/`
after changing the drawing.

`scripts/hive` drives it from the laptop: `status`, `setup`, `env`, `rebuild`, `logs`.

The database is backed up nightly at 04:30 to `~/hive-backups`, keeping 14.

## Working on it

```
cd backend && uv run pytest
cd frontend && npm run dev     # proxies /api to 127.0.0.1:8030
cd backend && HIVE_POLL=0 uv run uvicorn app.main:app --port 8030   # API without polling Hive
```

## Invariants

Each has a test that names it.

1. One bad poll sends nothing: a link alerts only after `CONFIRM_AFTER` consecutive bad polls. (`test_tracker.py::test_invariant_1_*`)
2. An outage sends exactly one down alert, however long it lasts. (`test_tracker.py::test_invariant_2_*`)
3. Every down alert gets one recovery notification with the outage length, even if the link passed through unknown. (`test_tracker.py::test_invariant_3_*`)
4. Only the first broken link in the chain is down; links behind it are unknown and send nothing. (`test_chain.py::test_invariant_4_*`)
5. When the Pi loses the internet, the internet link is down and Hive is unknown. (`test_chain.py::test_invariant_5_*`)
6. Losing the Hive login (SMS needed) shows as Hive cloud down and alerts, rather than going quiet. (`test_monitor.py::test_invariant_6_*`)
7. A failed push or a crash inside a poll doesn't stop the polling loop. (`test_monitor.py::test_invariant_7_*`)
8. The monitor only reads from Hive: every request it makes to Hive is a GET. (`test_hive.py::test_invariant_8_*`)
9. Device keys survive a restart, and login uses them without an SMS code. (`test_hive.py::test_invariant_9_*`)
10. Every confirmed state change is logged, except a link starting up healthy. (`test_monitor.py::test_invariant_10_*`)
11. Hot water switched off shows as a warning. (`test_chain.py::test_invariant_11_*`)
12. A wall thermostat battery under 20% shows as a warning. (`test_chain.py::test_invariant_12_*`)
13. The monitor watches the home that has a hub, even when it isn't the account's default, so an invited user's login works. (`test_hive.py::test_invariant_13_*`)
