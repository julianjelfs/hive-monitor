# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The whole household of one UK home, kids included. Most visits start from a push notification saying a link is down, or from someone wondering whether there will be hot water. Nobody in the house should need to know what a "boiler receiver" is to read the page; the person who maintains the system (the account holder's partner, an invited Hive user) does know, and uses the detail to decide what to reset.

## Product Purpose

Hive Monitor watches a Hive heating and hot water system that fails silently, and says so the moment it does. It polls Hive's cloud every minute, works out which link in the chain from the house's Pi to the boiler is broken, and pushes one alert per outage. The status page shows every link and where the chain breaks. Success: nobody in the house discovers a fault by stepping into a cold shower.

## Positioning

Hive's own app shows devices as a list and says nothing when they drop off. This shows the system as a chain, names the first broken link as the fault, and treats everything behind it as unknown rather than broken.

## Operating Context

- Opened on phones, often as an installed home-screen app, sometimes on a laptop.
- Usually reached from an ntfy push notification, which links to the page.
- Lives on the home network at hive.julianjelfs.co.uk, and on the tailnet away from home.
- The page refreshes itself every 10 seconds and when brought to the foreground.

## Capabilities and Constraints

- Read-only: it never sends commands to the heating.
- Links, in order: Pi to internet; Hive cloud; hub to Hive cloud; hub to boiler receiver; hot water; heating; hub to wall thermostat. The thermostat hangs off the hub, not the receiver. Hot water and heating depend on the receiver.
- States: working, check (warning), down, unknown. Unknown means "can't see past an upstream fault", never "broken".
- Warnings: hot water switched off; thermostat battery under 20%.
- Hardware in this house: Hive hub (NANO2), boiler receiver (SLR2, next to the boiler), wall thermostat (SLT3, in the hall), hot water cylinder, radiators. Two Hive bulbs exist on the account but are out of scope.
- Open decision: per-device "try this" fix suggestions are wanted; the wording must be confirmed by the user before it ships.

## Evidence on Hand

Live status from the real system via `/api/status`, and a change history. No photographs of the actual devices.

## Product Principles

1. One glance answers "is it working?". Everything else is secondary.
2. Point at the first broken link, never at its downstream victims.
3. Readable by anyone in the house; the technical detail is there for whoever fixes it.
4. Never show a stale or cached "all working".

## Accessibility & Inclusion

Children read it. State must never rely on colour alone; plain words for every state.
