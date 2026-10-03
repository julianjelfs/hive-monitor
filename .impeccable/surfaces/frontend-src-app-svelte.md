---
version: 1
slug: "frontend-src-app-svelte"
primary_target: "frontend/src/App.svelte"
related_targets: []
---

# Status page

Scope: the one page of Hive Monitor (frontend/src/App.svelte). Mode: Operate.

Audience and job: anyone in the house, often arriving from a push alert, asking "will there be hot water, and if not, what do I do?". The person who resets things needs to see which device and which connection failed.

Constraints: phone first, installed PWA, light and dark. State never by colour alone. Fix copy ("Try this" lines) approved by the user on 2026-10-03; do not reword without asking.

## Direction contract

THESIS: The heating system as a line diagram. Devices are stations, connections are track, and a fault is a closed section. Refuses the category default of a device list with status dots.

OWN-WORLD: Warm off-white ground (deep blue-black at night), navy ink, one green line colour for working track, hollow red track for a closed section, grey dashed track where we can't see. White interchange rings with drawn device pictograms. Humanist sans in the Johnston tradition (Cabin, self-hosted). Status rows in a ruled board.

STORY: The visitor reads three rows (hot water, heating, thermostat) and knows the answer. If something is wrong they see where the line breaks and a "Try this" line under the map.

FIRST VIEWPORT: Header (name, last check). Ruled status board, three rows, each with a plain state word. Then the line diagram from the Pi down to the boiler, with the thermostat on a 45-degree branch off the hub and hot water and heating on branches off the receiver. The fix notice sits under the map. Check now and Send test alert follow, then the service update history.

ADAPTATION: "Try this" sits directly under the status board, not under the map. Under the map it falls about 1000px down a 390px phone, out of the first viewport; the user asked for fix suggestions (2026-10-03) and PRODUCT principle 1 puts the answer in one glance.

FORM: Tube map with service status board, candidate 1 on my ordered list, taken as the pick card. Seed key e9718bec. Signature move: service health drawn as a transit map, a closed section rendered hollow.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
