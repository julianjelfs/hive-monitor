import type { HistoryEntry } from './api';

/** A history row, with how long an on or off lasted when it is one. */
export type Row = HistoryEntry & {
  // Milliseconds until the next on/off change, or until now for the latest.
  lasted?: number;
  // True for the latest on/off while we can still see it: it hasn't ended yet.
  ongoing?: boolean;
  // True when we lost sight of it before it changed, so it lasted at least this long.
  cut?: boolean;
};

const BLIND = new Set(['unknown', 'down']);

/**
 * Each on/off lasts until the next on/off change after it, or until we lost sight of the
 * link, whichever came first. Entries come newest first, so walking the list goes back in
 * time and each row's end is whatever was seen just before it in the list.
 */
export function withDurations(entries: HistoryEntry[], now: number): Row[] {
  let ends = now;
  let ongoing = true;
  let cut = false;
  return entries.map((e) => {
    const start = Date.parse(e.at);
    if (e.kind !== 'activity') {
      if (e.kind === 'state' && BLIND.has(e.new_state)) {
        ends = start;
        ongoing = false;
        cut = true;
      }
      return e;
    }
    const row: Row = { ...e, lasted: Math.max(0, ends - start), ongoing, cut };
    ends = start;
    ongoing = cut = false;
    return row;
  });
}

export interface Change {
  path: string;
  old: string | null;
  new: string;
}

/** Every field that changed on one poll, as one row. */
export interface Readings {
  at: string;
  kind: 'readings';
  changes: Change[];
  // The first poll that saw these fields: a baseline, not news.
  first: boolean;
}

// Readings that answer the question by themselves, so they get their own rows and always show.
export const HEADLINE = new Set(['schedule says', 'poll']);

/**
 * Fold each poll's readings into one row, leaving headline readings as rows of their own.
 * Entries come newest first and one poll's readings are next to each other.
 */
export function grouped(rows: Row[]): (Row | Readings)[] {
  const out: (Row | Readings)[] = [];
  for (const row of rows) {
    if (row.kind !== 'reading' || HEADLINE.has(row.path)) {
      out.push(row);
      continue;
    }
    const change = { path: row.path, old: row.old, new: row.new };
    const last = out[out.length - 1];
    if (last?.kind === 'readings' && last.at === row.at) {
      last.changes.push(change);
      last.first &&= row.old === null;
    } else {
      out.push({ at: row.at, kind: 'readings', changes: [change], first: row.old === null });
    }
  }
  for (const r of out) if (r.kind === 'readings') r.changes.sort((a, b) => a.path.localeCompare(b.path));
  return out;
}

const DAY_MINUTES = (m: number) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

/** A reading's value in words: times as times, schedules as slots, nothing as "none". */
export function shown(json: string | null): string {
  if (json === null) return 'not seen';
  let value: unknown;
  try {
    value = JSON.parse(json);
  } catch {
    return json;
  }
  if (value === null) return 'none';
  // Hive stamps events in milliseconds since 1970.
  if (typeof value === 'number' && value > 1e12) {
    return new Date(value).toLocaleString([], { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  }
  if (Array.isArray(value) && value.every((s) => s && typeof s === 'object' && 'start' in s)) {
    return value
      .map((s: { start: number; value?: Record<string, unknown> }) => {
        const v = s.value ?? {};
        const what = 'status' in v ? String(v.status).toLowerCase() : 'target' in v ? `${v.target}°` : JSON.stringify(v);
        return `${DAY_MINUTES(s.start)} ${what}`;
      })
      .join(', ');
  }
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

/** "45 min", "2 h 5 min", "3 days". */
export function span(ms: number): string {
  const m = Math.round(ms / 60_000);
  if (m < 1) return 'under a minute';
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 48) return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
  return `${Math.floor(h / 24)} days`;
}

export interface Day<T> {
  label: string;
  rows: T[];
}

/** Group rows (newest first) under "Today", "Yesterday" or the date. */
export function byDay<T extends { at: string }>(rows: T[], now: number): Day<T>[] {
  const today = new Date(now);
  const yesterday = new Date(now);
  yesterday.setDate(today.getDate() - 1);
  const days: Day<T>[] = [];
  for (const row of rows) {
    const d = new Date(row.at);
    const label =
      d.toDateString() === today.toDateString()
        ? 'Today'
        : d.toDateString() === yesterday.toDateString()
          ? 'Yesterday'
          : d.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' });
    const last = days[days.length - 1];
    if (last?.label === label) last.rows.push(row);
    else days.push({ label, rows: [row] });
  }
  return days;
}
