---
name: Hive Monitor
description: The household heating system drawn as a line diagram, with a status board on top.
colors:
  ground: "#f7f6f2"
  paper: "#ffffff"
  ink: "#14213d"
  muted: "#586074"
  rule: "#d9d6cd"
  line: "#0b6e4f"
  risk: "#d42b26"
  risk-text: "#b8211c"
  notice: "#e0a100"
  heat: "#f26b1d"
  heat-fill: "#ffe2cc"
  heat-text: "#b4500f"
  unknown: "#b4b2aa"
  none-fill: "#e7e5de"
  focus: "#1f5fd1"
  night-ground: "#0e1322"
  night-paper: "#151c2f"
  night-ink: "#e7eaf2"
  night-line: "#2bb07c"
  night-risk: "#ff5d52"
typography:
  title:
    fontFamily: "Cabin Variable, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  row:
    fontFamily: "Cabin Variable, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
  station:
    fontFamily: "Cabin Variable, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.25
  body:
    fontFamily: "Cabin Variable, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.45
  detail:
    fontFamily: "Cabin Variable, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.25
  chip:
    fontFamily: "Cabin Variable, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 700
    lineHeight: 1.2
rounded:
  chip: "4px"
  panel: "8px"
spacing:
  gutter: "16px"
  row: "12px 14px"
  section: "36px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.panel}"
    padding: "10px 18px"
    height: "44px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "10px 18px"
    height: "44px"
  chip-risk:
    backgroundColor: "{colors.risk}"
    textColor: "{colors.paper}"
    rounded: "{rounded.chip}"
    padding: "3px 9px"
  chip-notice:
    backgroundColor: "{colors.notice}"
    textColor: "{colors.ink}"
    rounded: "{rounded.chip}"
    padding: "3px 9px"
  chip-none:
    backgroundColor: "{colors.none-fill}"
    textColor: "{colors.muted}"
    rounded: "{rounded.chip}"
    padding: "3px 9px"
  status-board:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.panel}"
---

# Design System: Hive Monitor

## Overview

The heating system is a railway line. Devices are stations, connections are track, and a fault is a closed section drawn hollow, the way a transit map shows track out of service. Above the map, a ruled status board answers the household's question in three rows (hot water, heating, thermostat), each with one plain phrase: Good service, At risk, Switched off, Battery low, No information.

The page is a working tool opened from a push alert, usually on a phone. The board and the "Try this" line come first, then the map shows why. Everything is legible to a child; the technical detail sits in small muted text for whoever does the resetting.

## Colors

### Primary
- **Line green** (`line`): working track and good-service symbols. It is the line's own colour, so it means "running" and nothing else.

### State
- **Closure red** (`risk`): a closed section, an at-risk row, the fault station. `risk-text` is the darker red used for text on the light ground.
- **Notice amber** (`notice`): a warning, such as hot water switched off or a low battery. Text on amber is always ink.
- **Unknown grey** (`unknown`): track we can't see past. It always comes with a dash pattern, never as colour alone.

### Activity
- **Heat orange** (`heat`): hot water or heating running right now. It is a glow round the station and a warm station fill, never track, so it can't be mistaken for a state. `heat-text` is the darker orange for "On now" and "On" in text.

### Neutral
- **Map paper** (`ground`): warm off-white page ground. At night it becomes `night-ground`, a deep blue-black.
- **Paper** (`paper`): the board and notice panels.
- **Navy ink** (`ink`): text, station rings and rules.
- **Muted** (`muted`): detail text. **Rule** (`rule`): hairlines between rows.

### Named Rules
- **The Line Rule.** Green is the line. It never appears as decoration, a button or an accent.
- **The Not-Colour-Alone Rule.** Every state is carried twice: once in line form (solid, hollow, dashed) and once in words. Running is carried by the glow and the words "On now".

## Typography

Cabin, a humanist sans in the Johnston tradition, self-hosted through `@fontsource-variable/cabin`. One family carries everything.

### Hierarchy
- **Title** (700, 1.625rem): the "Hive" name only.
- **Row** (600, 1.125rem): status board row names.
- **Station** (600, 1rem): station names on the map.
- **Body** (400, 1rem): the fix line and notes.
- **Detail** (400, 0.8125rem, muted): device detail under stations; times use tabular numerals.
- **Chip** (700, 0.875rem): state phrases.

## Layout

A single column, at most 34rem wide, with a 16px gutter and safe-area insets for the installed app. The order is fixed: header, status board, "Try this", map, map key, actions, service updates. Each station opens its history at `#/history/<link>`, a second page in the same column. The map is an SVG on a 360-unit-wide grid with HTML labels laid over it at the same proportions, so labels wrap and stay real text. Stations sit 80 units apart on the trunk, and branches leave the trunk at 45 degrees from a single junction point.

## Elevation & Depth

Flat. Panels are separated by a 1.5px ink border, never by shadow. The only depth is the fault station's pulse ring and the static heat glow round a running station.

## Shapes

Panels have 8px corners and chips 4px. Station rings have a radius of 19.5 units with a 3-unit ink stroke. Track is 9 units wide with round joins.

## Components

### Status board
A ruled panel. Each row is a track symbol, a name, a state chip and an optional reason line. Good service shows as plain ink text with no chip fill.

### Track symbol
A 28×10 piece of track: solid green (good), solid amber (notice), hollow red (risk), dashed grey (no information). It leads each board row and makes up the map key, tying the board to the map.

### Line map (signature)
The signature component. Track takes the state of the link it leads into. A closed section is red with a ground-coloured core, so it reads as hollow. Unknown track is grey and dashed. The fault station gets a red ring and one slow pulse, which is static under reduced motion.

### Station history
A back link, the link's name and what it's doing now, then its changes grouped under "Today", "Yesterday" or the date, newest first. A state change shows its track symbol and state word. An on/off shows "On" in heat text or "Off" in ink, with how long it lasted. A trailing "›" on each map label says the station opens.

### Try this
A bordered panel with a "Try this" heading and the approved fix line for the fault, or one line per warning. The wording was approved by the household and lives in `frontend/src/lib/summary.ts`.

### Buttons
Primary is filled ink and secondary is outlined; both are 44px tall with a 1px press nudge.

## Do's and Don'ts

### Do:
- Put the household answer in the board, in plain words, before any diagram.
- Draw every state in line form as well as colour.
- Point at the first broken link only; everything behind it is grey and dashed.

### Don't:
- Don't use line green for anything except working track.
- Don't add a second animation. The fault pulse is the only motion; the heat glow stays still.
- Don't put coloured stripes on rows or panels; use the track symbol.
- Don't reword the "Try this" lines without asking the household.
