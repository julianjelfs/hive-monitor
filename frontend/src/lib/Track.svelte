<script lang="ts">
  import type { Tone } from './summary';

  // A short piece of the map's track, so a row or key carries its state in line form.
  let { tone }: { tone: Tone } = $props();
</script>

<svg class="track-symbol" viewBox="0 0 28 10" width="28" height="10" aria-hidden="true">
  {#if tone === 'none'}
    <path class="none" d="M3 5H25" />
  {:else}
    <path class={tone} d="M2 5H26" />
    {#if tone === 'risk'}<path class="hollow" d="M2 5H26" />{/if}
  {/if}
</svg>

<style>
  .track-symbol {
    flex: none;
    display: block;
  }
  path {
    fill: none;
    stroke-width: 7;
  }
  .good {
    stroke: var(--line);
  }
  .notice {
    stroke: var(--notice);
  }
  .risk {
    stroke: var(--risk);
  }
  .hollow {
    stroke: var(--hollow, var(--paper));
    stroke-width: 2.5;
  }
  .none {
    stroke: var(--unknown);
    stroke-width: 4.5;
    stroke-dasharray: 2 5;
    stroke-linecap: round;
  }
</style>
