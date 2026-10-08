<script lang="ts">
  import { onMount } from 'svelte';
  import { getHistory, type History, type Link } from './api';
  import { byDay, grouped, shown, span, withDurations } from './history';
  import Track from './Track.svelte';
  import { STATE_WORD } from './summary';

  let { linkKey, link, now }: { linkKey: string; link: Link | undefined; now: number } = $props();

  let history = $state<History | null>(null);
  let failed = $state(false);
  // Hive's raw fields are for whoever is digging; remember the choice on this phone.
  let raw = $state(readRaw());

  function readRaw(): boolean {
    try {
      return localStorage.getItem('hive-raw') !== 'off';
    } catch {
      return true;
    }
  }

  function setRaw(on: boolean) {
    raw = on;
    try {
      localStorage.setItem('hive-raw', on ? 'on' : 'off');
    } catch {
      // Private mode or blocked storage: the choice lasts until the page closes.
    }
  }

  async function load() {
    try {
      history = await getHistory(linkKey);
      failed = false;
    } catch {
      failed = true;
    }
  }

  onMount(() => {
    load();
    const poll = setInterval(load, 15_000);
    const onVisible = () => document.visibilityState === 'visible' && load();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(poll);
      document.removeEventListener('visibilitychange', onVisible);
    };
  });

  // Only hot water and heating have an on/off; the rest log state changes alone.
  const switches = $derived(linkKey === 'hotwater' || linkKey === 'heating');
  const rows = $derived(
    history ? grouped(withDurations(history.entries, now)).filter((r) => raw || r.kind !== 'readings') : []
  );
  const days = $derived(byDay(rows, now));

  function time(iso: string): string {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  const TONE_OF = { ok: 'good', warn: 'notice', down: 'risk', unknown: 'none' } as const;
</script>

<header class="top">
  <a class="back" href="#/">‹ Map</a>
</header>

<h1 class="history-title">{history?.label ?? link?.label ?? 'History'}</h1>
{#if link}
  <p class="history-now">
    {#if link.active === true}<span class="on-now">On now.</span>{:else if link.active === false}Off now.{/if}
    {link.detail}
  </p>
{/if}

<label class="raw-toggle">
  <input type="checkbox" checked={raw} onchange={(e) => setRaw(e.currentTarget.checked)} />
  Show every field Hive reports
</label>

{#if failed && !history}
  <p class="note">Couldn't load the history. The Pi may not be answering.</p>
{:else if history && !days.length}
  <p class="note">
    Nothing recorded yet.
    {switches ? 'Each time it comes on or goes off, it appears here.' : 'Each change in its state appears here.'}
  </p>
{:else}
  {#each days as day (day.label)}
    <section class="history-day">
      <h2>{day.label}</h2>
      <ol>
        {#each day.rows as row (row.at + row.kind)}
          <li>
            <time datetime={row.at}>{time(row.at)}</time>
            {#if row.kind === 'activity'}
              <span class="what">
                <span class="switch" class:on={row.active}>{row.active ? 'On' : 'Off'}</span>
                {#if row.lasted !== undefined}
                  <span class="lasted">{row.ongoing
                      ? `${span(row.lasted)} so far`
                      : row.cut
                        ? `for at least ${span(row.lasted)}, then lost sight`
                        : `for ${span(row.lasted)}`}</span>
                {/if}
              </span>
            {:else if row.kind === 'state'}
              <span class="what">
                <span class="change"><Track tone={TONE_OF[row.new_state]} />{STATE_WORD[row.new_state]}</span>
                <span class="lasted">{row.detail}</span>
              </span>
            {:else if row.kind === 'reading' && row.path === 'schedule says'}
              <span class="what">
                <span class="change">Schedule says {row.new === 'true' ? 'on' : 'off'}</span>
                <span class="lasted">From Hive's schedule for this time of day</span>
              </span>
            {:else if row.kind === 'reading'}
              <span class="what">
                {#if row.new === '"ok"'}
                  <span class="change">Reached Hive</span>
                {:else}
                  <span class="change failed">A check failed</span>
                  <span class="lasted">{shown(row.new)}</span>
                {/if}
              </span>
            {:else if row.first}
              <details class="what readings">
                <summary>Started recording {row.changes.length} fields</summary>
                <dl>
                  {#each row.changes as c (c.path)}
                    <dt>{c.path}</dt>
                    <dd>{shown(c.new)}</dd>
                  {/each}
                </dl>
              </details>
            {:else}
              <dl class="what readings">
                {#each row.changes as c (c.path)}
                  <dt>{c.path}</dt>
                  <dd>{shown(c.old)} → {shown(c.new)}</dd>
                {/each}
              </dl>
            {/if}
          </li>
        {/each}
      </ol>
    </section>
  {/each}
{/if}

<style>
  .back {
    display: inline-flex;
    align-items: center;
    min-height: 44px;
    color: var(--ink);
    font-weight: 700;
    text-decoration: none;
  }
  .back:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  .history-title {
    margin: 0;
  }
  .history-now {
    margin: 4px 0 0;
    color: var(--muted);
  }
  .on-now {
    font-weight: 700;
    color: var(--heat-text);
  }

  .history-day {
    margin-top: 28px;
  }
  h2 {
    margin: 0 0 6px;
    font-size: 1.0625rem;
    font-weight: 700;
  }
  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    border-top: 1.5px solid var(--ink);
  }
  li {
    display: grid;
    grid-template-columns: 3.75rem 1fr;
    align-items: baseline;
    gap: 10px;
    padding: 9px 0;
    border-bottom: 1px solid var(--rule);
  }
  time {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .what {
    display: flex;
    flex-direction: column;
  }
  .switch,
  .change {
    font-weight: 700;
  }
  .switch.on {
    color: var(--heat-text);
  }
  .change {
    display: flex;
    align-items: center;
    gap: 8px;
    --hollow: var(--ground);
  }
  .change.failed {
    color: var(--risk-text);
  }

  .raw-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    margin-top: 8px;
    font-size: 0.875rem;
    color: var(--muted);
  }
  .raw-toggle input {
    width: 18px;
    height: 18px;
    accent-color: var(--ink);
  }

  /* Hive's raw fields: small and muted, for whoever does the digging. */
  .readings {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--muted);
    min-width: 0;
  }
  .readings summary {
    cursor: pointer;
    min-height: 24px;
  }
  dl.readings,
  .readings dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 2px 10px;
    margin: 0;
  }
  .readings dt {
    font: 0.75rem/1.5 ui-monospace, 'SF Mono', Menlo, monospace;
    color: var(--ink);
  }
  .readings dd {
    margin: 0;
    overflow-wrap: anywhere;
    font-variant-numeric: tabular-nums;
  }

  .lasted {
    font-size: 0.875rem;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
</style>
