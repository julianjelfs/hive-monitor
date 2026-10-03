<script lang="ts">
  import type { Link, LinkState } from './api';
  import { STATE_WORD } from './summary';

  let { links, fault, clock }: { links: Link[]; fault: string | null; clock: (iso: string) => string } = $props();

  // The diagram is fixed: the house has one of each device. Coordinates are in a 360-wide
  // viewBox; labels are HTML laid over it at the same proportions so they wrap and stay text.
  const W = 360;
  const H = 684;
  const TRUNK = 36;

  interface Station {
    key: string; // the link whose state colours this station and the track into it
    icon: string;
    name: string;
    x: number;
    y: number;
  }

  const stations: Station[] = [
    { key: 'pi', icon: 'pi', name: 'This Pi', x: TRUNK, y: 28 },
    { key: 'internet', icon: 'internet', name: 'Internet', x: TRUNK, y: 108 },
    { key: 'hive', icon: 'hive', name: 'Hive cloud', x: TRUNK, y: 188 },
    { key: 'hub', icon: 'hub', name: 'Hub', x: TRUNK, y: 268 },
    { key: 'thermostat', icon: 'thermostat', name: 'Wall thermostat', x: 196, y: 360 },
    { key: 'receiver', icon: 'receiver', name: 'Boiler receiver', x: TRUNK, y: 452 },
    { key: 'heating', icon: 'heating', name: 'Heating', x: 196, y: 552 },
    { key: 'hotwater', icon: 'hotwater', name: 'Hot water', x: TRUNK, y: 640 }
  ];

  // Each piece of track carries the state of the link it leads into.
  const tracks: { key: string; d: string }[] = [
    { key: 'internet', d: `M${TRUNK} 28V108` },
    { key: 'hive', d: `M${TRUNK} 108V188` },
    { key: 'hub', d: `M${TRUNK} 188V268` },
    { key: 'thermostat', d: `M${TRUNK} 320L${TRUNK + 40} 360H196` },
    { key: 'receiver', d: `M${TRUNK} 268V452` },
    { key: 'heating', d: `M${TRUNK} 512L${TRUNK + 40} 552H196` },
    { key: 'hotwater', d: `M${TRUNK} 452V640` }
  ];

  const byKey = $derived(new Map(links.map((l) => [l.key, l])));

  // The Pi is the monitor itself: if this page has data, it is running.
  function stateOf(key: string): LinkState {
    if (key === 'pi') return 'ok';
    return byKey.get(key)?.state ?? 'unknown';
  }

  function detailOf(key: string): string {
    if (key === 'pi') return 'Checking every minute';
    return byKey.get(key)?.detail ?? '';
  }

  const pct = (v: number, of: number) => `${(v / of) * 100}%`;
</script>

<figure class="map" aria-label="How the heating system connects">
  <svg viewBox="0 0 {W} {H}" aria-hidden="true">
    <!-- Draw the track that leads somewhere unknown first, so live track sits on top at the joins. -->
    {#each [...tracks].sort((a, b) => (stateOf(a.key) === 'unknown' ? -1 : 0) - (stateOf(b.key) === 'unknown' ? -1 : 0)) as t (t.key)}
      {@const s = stateOf(t.key)}
      <path class="track {s}" d={t.d} />
      {#if s === 'down'}<path class="track-hollow" d={t.d} />{/if}
    {/each}

    {#each stations as st (st.key)}
      {@const s = stateOf(st.key)}
      {#if st.key === fault}
        <circle class="pulse" cx={st.x} cy={st.y} r="17" />
      {/if}
      <circle class="ring {s}" cx={st.x} cy={st.y} r="17" />
      <use class="glyph {s}" href="#p-{st.icon}" x={st.x - 10} y={st.y - 10} width="20" height="20" />
    {/each}
  </svg>

  <ol class="labels">
    {#each stations as st (st.key)}
      {@const s = stateOf(st.key)}
      {@const link = byKey.get(st.key)}
      <li
        class="label {s}"
        style="left:{pct(st.x + 28, W)};top:{pct(st.y - 13, H)};max-width:calc({pct(W - st.x - 30, W)})"
      >
        <span class="name">{st.name}</span>
        <span class="state-word">{STATE_WORD[s]}</span>
        <span class="detail">{detailOf(st.key)}</span>
        {#if link?.since && (s === 'down' || s === 'warn')}
          <span class="since">Since {clock(link.since)}</span>
        {/if}
      </li>
    {/each}
  </ol>
</figure>

<style>
  .map {
    position: relative;
    margin: 26px 0 12px;
    aspect-ratio: 360 / 684;
  }

  svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    overflow: visible;
  }

  .track {
    fill: none;
    stroke-width: 9;
    stroke-linejoin: round;
    transition: stroke 240ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  .track.ok {
    stroke: var(--line);
  }
  .track.warn {
    stroke: var(--notice);
  }
  .track.down {
    stroke: var(--risk);
  }
  /* A closed section is drawn hollow, the way a map shows track out of service. */
  .track-hollow {
    fill: none;
    stroke: var(--ground);
    stroke-width: 3.5;
    stroke-linejoin: round;
  }
  /* Unknown track is grey and broken, so it reads without colour. */
  .track.unknown {
    stroke: var(--unknown);
    stroke-dasharray: 3 7;
    stroke-linecap: round;
    stroke-width: 6;
  }

  .ring {
    fill: var(--station);
    stroke: var(--ink);
    stroke-width: 3;
    transition: stroke 240ms cubic-bezier(0.16, 1, 0.3, 1);
  }
  .ring.down {
    stroke: var(--risk);
    stroke-width: 4;
  }
  .ring.warn {
    stroke: var(--notice);
    stroke-width: 4;
  }
  .ring.unknown {
    stroke: var(--unknown);
  }

  .glyph {
    color: var(--ink);
  }
  .glyph.down {
    color: var(--risk);
  }
  .glyph.unknown {
    color: var(--muted);
  }

  .pulse {
    fill: none;
    stroke: var(--risk);
    stroke-width: 2;
    transform-box: fill-box;
    transform-origin: center;
    animation: pulse 2s cubic-bezier(0.16, 1, 0.3, 1) infinite;
  }
  @keyframes pulse {
    from {
      opacity: 0.7;
      transform: scale(1);
    }
    to {
      opacity: 0;
      transform: scale(1.9);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .pulse {
      animation: none;
      opacity: 0.35;
      transform: scale(1.4);
    }
  }

  .labels {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .label {
    position: absolute;
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }

  .name {
    font-weight: 600;
    font-size: 1rem;
    color: var(--ink);
  }
  .label.down .name {
    color: var(--risk-text);
  }
  .label.unknown .name {
    color: var(--muted);
  }

  /* Screen readers get the state in words; sighted readers get it from the drawing and detail. */
  .state-word {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  .detail,
  .since {
    font-size: 0.8125rem;
    color: var(--muted);
  }
  .since {
    font-variant-numeric: tabular-nums;
  }
  .label.down .since {
    color: var(--risk-text);
    font-weight: 600;
  }
</style>
