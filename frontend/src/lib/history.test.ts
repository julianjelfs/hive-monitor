import { describe, expect, it } from 'vitest';
import type { HistoryEntry } from './api';
import { byDay, span, withDurations } from './history';

const at = (hhmm: string, day = 8) => `2026-10-0${day}T${hhmm}:00`;
const MIN = 60_000;

const on = (t: string, day?: number): HistoryEntry => ({ at: at(t, day), kind: 'activity', active: true });
const off = (t: string, day?: number): HistoryEntry => ({ at: at(t, day), kind: 'activity', active: false });
const unknown = (t: string): HistoryEntry => ({
  at: at(t),
  kind: 'state',
  old_state: 'ok',
  new_state: 'unknown',
  detail: "Can't see past Hub",
  alert: null
});

describe('withDurations', () => {
  it('invariant 20: each on or off lasts until the next on/off change, and the latest until now', () => {
    const now = Date.parse(at('09:30'));
    const rows = withDurations([off('09:00'), on('08:15'), off('06:00')], now);
    expect(rows.map((r) => [r.lasted, r.ongoing, r.cut])).toEqual([
      [30 * MIN, true, false],
      [45 * MIN, false, false],
      [135 * MIN, false, false]
    ]);
  });

  it('invariant 20: losing sight of the link ends an on or off early, as "at least"', () => {
    const now = Date.parse(at('09:30'));
    const rows = withDurations([off('09:00'), unknown('08:50'), on('08:15'), unknown('07:00'), off('06:00')], now);
    expect(rows.map((r) => [r.kind, r.lasted, r.ongoing, r.cut])).toEqual([
      ['activity', 30 * MIN, true, false],
      ['state', undefined, undefined, undefined],
      ['activity', 35 * MIN, false, true],
      ['state', undefined, undefined, undefined],
      ['activity', 60 * MIN, false, true]
    ]);
  });
});

describe('span', () => {
  it('reads in minutes, hours, then days', () => {
    expect(span(20_000)).toBe('under a minute');
    expect(span(45 * MIN)).toBe('45 min');
    expect(span(120 * MIN)).toBe('2 h');
    expect(span(125 * MIN)).toBe('2 h 5 min');
    expect(span(72 * 60 * MIN)).toBe('3 days');
  });
});

describe('byDay', () => {
  it('groups newest-first rows under today, yesterday, then the date', () => {
    const days = byDay(withDurations([on('07:00'), off('22:00', 7), on('21:00', 7), off('08:00', 5)], 0), Date.parse(at('12:00')));
    expect(days.map((d) => [d.label, d.rows.length])).toEqual([
      ['Today', 1],
      ['Yesterday', 2],
      [new Date(at('08:00', 5)).toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' }), 1]
    ]);
  });
});
