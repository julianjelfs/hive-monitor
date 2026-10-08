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

## Design

The page draws the system as a line diagram: devices are stations, connections are track, and a fault shows as a closed section. `DESIGN.md` records the system and `PRODUCT.md` who it's for. The "Try this" wording in `frontend/src/lib/summary.ts` was approved by the household; ask before changing it.

## History

Tap a station on the map to see its history, newest first. Every station logs its state
changes. Hot water and heating also log each time they come on or go off, read from Hive on
every poll, and their stations glow orange on the map while they're running. The log keeps
on/off times only from the day this went in.

When the monitor loses sight of hot water or heating, it writes no on/off. The history shows
the gap as "No information", and the on or off before it reads "for at least".

It also logs every field Hive reports for the hub, receiver, thermostat, hot water and
heating, whenever one changes: mode, boost, status, "working", schedules, signal, battery,
and Hive's own `presenceLastChanged` stamp, which catches offline blips between polls. Hub
uptime is logged only when it drops, so a row means the hub restarted. Each failed poll is
logged with its reason, even a single one. And "schedule says" records what Hive's own
schedule wants hot water doing, in house time (`HIVE_TIMEZONE`, default Europe/London), so
a scheduled "on" with no "On" after it stands out.

All of it is on each station's history page. `GET /api/readings?limit=N` returns every
link's readings at once, newest first.

History keeps 14 days (`HIVE_RETENTION_DAYS`). Once a day the monitor deletes older state
changes, on/off times and readings, but keeps the newest row for each field so a restart
doesn't log it all again. SQLite reuses the freed space, so the file stops growing at
about two weeks' worth.

## Alerts

Alerts go through [ntfy](https://ntfy.sh). Install the ntfy app, subscribe to the topic
named in the Pi's `backend/.env`, and press "Send test alert" on the status page to check.

- A link alerts after two bad polls in a row, so about two minutes after it breaks.
- One alert per outage, and one "back" message when it recovers, with how long it was down.
- Warnings (hot water switched off, thermostat battery under 20%) show on the page but
  don't notify.
- For troubleshooting, `NOTIFY_ACTIVITY=hotwater` (or `hotwater,heating`) in the Pi's `.env`
  pushes every on/off change of those links, quietly. Remove the line and restart to stop.

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
cd frontend && npm test
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
14. The status board never says "at risk" when all we've lost is the view: the internet or Hive cloud being down reads as "No information". (`frontend/src/lib/summary.test.ts`, "invariant 14")
15. Only the first broken link gets a "Try this" line; links behind it get none. (`frontend/src/lib/summary.test.ts`, "invariant 15")
16. Hot water is on when Hive says it's heating water, and heating is on when the boiler is firing. A link behind a dead one is neither on nor off. (`test_chain.py::test_invariant_16_*`)
17. Each on/off change writes one row. Polls that see no change write nothing, and nor does a restart. (`test_monitor.py::test_invariant_17_*`)
18. A link the monitor can't see writes no on/off, so a gap never reads as "off". (`test_monitor.py::test_invariant_18_*`)
19. A link's history holds its own state, on/off and reading changes, newest first, and no other link's. (`test_api.py::test_invariant_19_*`)
20. On the history page, each on or off lasts until the next on/off change or until the monitor lost sight of the link, whichever came first. (`frontend/src/lib/history.test.ts`, "invariant 20")
21. A change in any field Hive reports for a heating device writes one row. No change, or a restart, writes nothing. (`test_monitor.py::test_invariant_21_*`)
22. Fields that tick by themselves write nothing: `lastSeen` never, and the hub's uptime only when it falls. (`test_readings.py::test_invariant_22_*`)
23. A single failed poll is logged with its reason, though no link changes state, and devices keep their last readings. (`test_monitor.py::test_invariant_23_*`)
24. "Schedule says" is the hot water schedule slot in force at the house's local time, carrying over from the day before. (`test_readings.py::test_invariant_24_*`)
25. One poll's readings show as one history row, and "schedule says" and poll results always get rows of their own. (`frontend/src/lib/history.test.ts`, "invariant 25")
26. History older than the retention period is deleted, except each reading's and each link's newest on/off, so a restart logs nothing already known. (`test_monitor.py::test_invariant_26_*`)
