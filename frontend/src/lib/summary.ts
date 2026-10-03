import type { Link, LinkState } from './api';

/** What the household reads first: three rows, each a plain answer. */
export type Tone = 'good' | 'risk' | 'notice' | 'none';

export interface Row {
  key: 'hotwater' | 'heating' | 'thermostat';
  label: string;
  word: string;
  tone: Tone;
  reason: string;
}

// The links each answer depends on, from the Pi outwards.
const PATHS: Record<Row['key'], string[]> = {
  hotwater: ['internet', 'hive', 'hub', 'receiver', 'hotwater'],
  heating: ['internet', 'hive', 'hub', 'receiver', 'heating'],
  thermostat: ['internet', 'hive', 'hub', 'thermostat']
};

const LABELS: Record<Row['key'], string> = {
  hotwater: 'Hot water',
  heating: 'Heating',
  thermostat: 'Thermostat'
};

// Losing sight of Hive says nothing about the boiler, so these never read as "at risk".
const BLIND_SPOTS = new Set(['internet', 'hive']);

export function rows(links: Link[]): Row[] {
  const byKey = new Map(links.map((l) => [l.key, l]));
  return (Object.keys(PATHS) as Row['key'][]).map((key) => {
    const label = LABELS[key];
    const path = PATHS[key].map((k) => byKey.get(k));
    if (path.some((l) => !l)) {
      return { key, label, word: 'No information', tone: 'none', reason: 'Waiting for the first check' };
    }
    const fault = path.find((l) => l!.state === 'down');
    if (fault) {
      if (BLIND_SPOTS.has(fault.key)) {
        return { key, label, word: 'No information', tone: 'none', reason: `${fault.label} is down, so we can't see` };
      }
      if (key === 'thermostat' && fault.key === 'thermostat') {
        return { key, label, word: 'Offline', tone: 'risk', reason: fault.detail };
      }
      return { key, label, word: 'At risk', tone: 'risk', reason: `${deviceName(fault)} is offline` };
    }
    const own = byKey.get(key)!;
    if (own.state === 'warn') {
      const word = key === 'thermostat' ? 'Battery low' : 'Switched off';
      return { key, label, word, tone: 'notice', reason: own.detail };
    }
    return { key, label, word: 'Good service', tone: 'good', reason: '' };
  });
}

function deviceName(link: Link): string {
  return (
    {
      hub: 'The hub',
      receiver: 'The boiler receiver',
      hotwater: 'Hot water control',
      heating: 'Heating control'
    }[link.key] ?? link.label
  );
}

/** The approved "Try this" lines. Reword only with the household's say-so. */
const FIXES: Record<string, string> = {
  internet:
    'Check the broadband router. If its lights are off or red, switch it off at the wall for 30 seconds, then on again.',
  hive: "Nothing to fix at home. Hive's servers aren't answering; this usually clears on its own.",
  hub: 'Switch the hub off at the plug for 10 seconds, then on. Check its cable to the router is in.',
  receiver: 'Switch the receiver off at its wall switch by the boiler for 10 seconds, then on.',
  thermostat: "Replace the thermostat's batteries, then give it a few minutes to reconnect."
};

const WARN_FIXES: Record<string, string> = {
  hotwater: 'Turn hot water back to Schedule in the Hive app.',
  thermostat: "Replace the thermostat's batteries soon."
};

const DEVICE: Record<string, string> = {
  internet: 'Broadband',
  hive: 'Hive cloud',
  hub: 'Hub',
  receiver: 'Boiler receiver',
  thermostat: 'Thermostat',
  hotwater: 'Hot water',
  heating: 'Heating'
};

export interface Fix {
  key: string;
  label: string;
  text: string;
}

/** What to try: the fault's line if there is one, otherwise a line per warning. */
export function fixes(links: Link[], fault: string | null): Fix[] {
  if (fault) {
    const link = links.find((l) => l.key === fault);
    let text = FIXES[fault];
    if (!link || !text) return [];
    if (fault === 'hive' && /SMS|setup/i.test(link.detail)) {
      text = 'Hive wants a new SMS code: run `hive setup` on the laptop.';
    }
    return [{ key: fault, label: DEVICE[fault] ?? link.label, text }];
  }
  return links
    .filter((l) => l.state === 'warn' && WARN_FIXES[l.key])
    .map((l) => ({ key: l.key, label: DEVICE[l.key] ?? l.label, text: WARN_FIXES[l.key] }));
}

const TROUBLE = new Set(['down', 'warn']);

/** History rows worth reading: going into trouble, or coming out of it. */
export function worthShowing(e: { old_state: LinkState; new_state: LinkState }): boolean {
  return TROUBLE.has(e.new_state) || TROUBLE.has(e.old_state);
}

export const STATE_WORD: Record<LinkState, string> = {
  ok: 'Working',
  warn: 'Needs a look',
  down: 'Closed',
  unknown: 'No information'
};
