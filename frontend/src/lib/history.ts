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
      if (BLIND.has(e.new_state)) {
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

/** "45 min", "2 h 5 min", "3 days". */
export function span(ms: number): string {
  const m = Math.round(ms / 60_000);
  if (m < 1) return 'under a minute';
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60);
  if (h < 48) return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
  return `${Math.floor(h / 24)} days`;
}

export interface Day {
  label: string;
  rows: Row[];
}

/** Group rows (newest first) under "Today", "Yesterday" or the date. */
export function byDay(rows: Row[], now: number): Day[] {
  const today = new Date(now);
  const yesterday = new Date(now);
  yesterday.setDate(today.getDate() - 1);
  const days: Day[] = [];
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
