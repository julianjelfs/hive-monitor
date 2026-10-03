<script lang="ts">
  import { onMount } from 'svelte';
  import { checkNow, getStatus, testPush, type Status } from './lib/api';
  import LineMap from './lib/LineMap.svelte';
  import Pictograms from './lib/Pictograms.svelte';
  import Track from './lib/Track.svelte';
  import { STATE_WORD, fixes, rows, worthShowing } from './lib/summary';

  let status = $state<Status | null>(null);
  let unreachable = $state(false);
  let now = $state(Date.now());
  let checking = $state(false);
  let pushNote = $state('');

  async function refresh() {
    try {
      status = await getStatus();
      unreachable = false;
    } catch {
      unreachable = true;
    }
  }

  async function onCheck() {
    checking = true;
    const before = status?.checked_at;
    await checkNow();
    // The poll takes a second or two; wait for a newer result rather than guessing.
    for (let i = 0; i < 20 && status?.checked_at === before; i++) {
      await new Promise((r) => setTimeout(r, 500));
      await refresh();
    }
    checking = false;
  }

  async function onTestPush() {
    pushNote = 'Sending…';
    pushNote = await testPush();
  }

  onMount(() => {
    refresh();
    const poll = setInterval(refresh, 10_000);
    const tick = setInterval(() => (now = Date.now()), 1_000);
    // An installed app comes back from the background showing whatever it last saw.
    // Fetch straight away rather than show a stale answer for up to ten seconds.
    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        now = Date.now();
        refresh();
      }
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
      document.removeEventListener('visibilitychange', onVisible);
    };
  });

  const links = $derived(status?.links ?? []);
  const board = $derived(rows(links));
  const tryThis = $derived(fixes(links, status?.fault ?? null));
  const updates = $derived((status?.events ?? []).filter(worthShowing));
  const stale = $derived(
    status?.checked_at != null && now - Date.parse(status.checked_at) > status.interval * 3_000
  );

  function ago(iso: string | null): string {
    if (!iso) return 'not yet';
    const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
    if (s < 60) return `${s}s ago`;
    const m = Math.round(s / 60);
    if (m < 60) return `${m} min ago`;
    const h = Math.floor(m / 60);
    if (h < 48) return `${h} h ${m % 60} min ago`;
    return `${Math.floor(h / 24)} days ago`;
  }

  function clock(iso: string): string {
    const d = new Date(iso);
    const today = new Date(now).toDateString() === d.toDateString();
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return today ? time : `${d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })} ${time}`;
  }

  const TONE_OF = { ok: 'good', warn: 'notice', down: 'risk', unknown: 'none' } as const;
</script>

<Pictograms />

<main>
  <header class="top">
    <h1>Hive</h1>
    {#if status}
      <p class="checked" class:late={stale}>
        Checked {ago(status.checked_at)}
      </p>
    {/if}
  </header>

  {#if unreachable}
    <section class="board" aria-live="polite">
      <div class="row">
        <span class="row-name"><Track tone="risk" />Monitor</span>
        <span class="chip risk">Not answering</span>
      </div>
      <p class="board-note">
        The Pi isn't answering. It may be off, or this phone isn't on the home network or tailnet.
      </p>
    </section>
  {:else}
    <section class="board" aria-label="Service status" aria-live="polite">
      {#each board as row (row.key)}
        <div class="row">
          <span class="row-name"><Track tone={row.tone} />{row.label}</span>
          <span class="chip {row.tone}">{row.word}</span>
          {#if row.reason}<span class="row-reason">{row.reason}</span>{/if}
        </div>
      {/each}
    </section>
  {/if}

  {#if stale && !unreachable}
    <p class="stalled" role="alert">The monitor has stopped checking. Alerts won't arrive until it starts again.</p>
  {/if}

  {#if tryThis.length}
    <section class="try">
      <h2>Try this</h2>
      {#each tryThis as f (f.key)}
        <p>
          {#if tryThis.length > 1}<strong>{f.label}.</strong>{/if}
          {#each f.text.split('`') as part, i}{#if i % 2}<code>{part}</code>{:else}{part}{/if}{/each}
        </p>
      {/each}
    </section>
  {/if}

  {#if links.length}
    <LineMap {links} fault={status?.fault ?? null} {clock} />
    <ul class="key" aria-label="Map key">
      <li><Track tone="good" />Working</li>
      <li><Track tone="risk" />Closed</li>
      <li><Track tone="notice" />Needs a look</li>
      <li><Track tone="none" />No information</li>
    </ul>
  {/if}

  <div class="actions">
    <button class="primary" onclick={onCheck} disabled={checking}>{checking ? 'Checking…' : 'Check now'}</button>
    <button class="secondary" onclick={onTestPush}>Send test alert</button>
  </div>
  {#if pushNote}<p class="note" aria-live="polite">{pushNote}</p>{/if}
  {#if status && !status.push_configured}
    <p class="note">Alerts are off: NTFY_TOPIC isn't set on the Pi.</p>
  {/if}

  {#if updates.length}
    <section class="updates">
      <h2>Service updates</h2>
      <ol>
        {#each updates as e}
          <li>
            <time datetime={e.at}>{clock(e.at)}</time>
            <span class="update-name">{e.label}</span>
            <span class="chip small {TONE_OF[e.new_state]}">{STATE_WORD[e.new_state]}</span>
          </li>
        {/each}
      </ol>
    </section>
  {/if}
</main>
