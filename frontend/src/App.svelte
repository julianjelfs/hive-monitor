<script lang="ts">
  import { onMount } from 'svelte';
  import { checkNow, getStatus, testPush, type Link, type Status } from './lib/api';

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

  const fault = $derived(status?.links.find((l) => l.key === status?.fault) ?? null);
  const warnings = $derived(status?.links.filter((l) => l.state === 'warn') ?? []);
  const stale = $derived(
    status?.checked_at != null && now - Date.parse(status.checked_at) > status.interval * 3_000
  );

  function ago(iso: string | null): string {
    if (!iso) return 'never';
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

  const word: Record<Link['state'], string> = {
    ok: 'Working',
    warn: 'Check',
    down: 'Down',
    unknown: 'Unknown'
  };
</script>

<main>
  <header>
    <h1>Hive</h1>
    {#if status}
      <p class="checked" class:late={stale}>Checked {ago(status.checked_at)}</p>
    {/if}
  </header>

  {#if stale && !unreachable}
    <p class="stalled">The monitor has stopped checking. Alerts won't arrive until it starts again.</p>
  {/if}

  {#if unreachable}
    <section class="summary down">
      <h2>Can't reach the monitor</h2>
      <p>The Pi isn't answering. It may be off, or this device isn't on the home network.</p>
    </section>
  {:else if !status || status.links.length === 0}
    <section class="summary unknown">
      <h2>Starting up</h2>
      <p>The first check is on its way.</p>
    </section>
  {:else if fault}
    <section class="summary down">
      <h2>{fault.label} is down</h2>
      <p>{fault.detail}</p>
      {#if fault.since}<p class="small">Since {clock(fault.since)}</p>{/if}
    </section>
  {:else if warnings.length}
    <section class="summary warn">
      <h2>Working, with {warnings.length === 1 ? 'one thing' : `${warnings.length} things`} to look at</h2>
      {#each warnings as w}<p>{w.label}: {w.detail}</p>{/each}
    </section>
  {:else}
    <section class="summary ok">
      <h2>Everything's working</h2>
      <p>Every link from the Pi to the boiler is up.</p>
    </section>
  {/if}

  {#if status && status.links.length}
    <ol class="chain">
      {#each status.links as link (link.key)}
        <li class={link.state}>
          <span class="dot" aria-hidden="true"></span>
          <div class="body">
            <div class="row">
              <span class="label">{link.label}</span>
              <span class="badge">{word[link.state]}</span>
            </div>
            <p class="detail">{link.detail}</p>
            {#if link.since && (link.state === 'down' || link.state === 'warn')}
              <p class="small">Since {clock(link.since)}</p>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  {/if}

  <div class="actions">
    <button onclick={onCheck} disabled={checking}>{checking ? 'Checking…' : 'Check now'}</button>
    <button class="quiet" onclick={onTestPush}>Send test alert</button>
  </div>
  {#if pushNote}<p class="small note">{pushNote}</p>{/if}
  {#if status && !status.push_configured}
    <p class="small note">Alerts are off: NTFY_TOPIC isn't set on the Pi.</p>
  {/if}

  {#if status?.events.length}
    <section class="history">
      <h3>Changes</h3>
      <ul>
        {#each status.events as e}
          <li>
            <time>{clock(e.at)}</time>
            <span class="pill {e.new_state}">{word[e.new_state]}</span>
            <span>{e.label}{#if e.alert}<span class="alerted">&nbsp;· alerted</span>{/if}</span>
          </li>
        {/each}
      </ul>
    </section>
  {/if}
</main>
