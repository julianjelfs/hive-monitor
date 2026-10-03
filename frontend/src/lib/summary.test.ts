import { describe, expect, it } from 'vitest';
import type { Link, LinkState } from './api';
import { fixes, rows, worthShowing } from './summary';

const KEYS = ['internet', 'hive', 'hub', 'receiver', 'hotwater', 'heating', 'thermostat'];

function chain(overrides: Record<string, LinkState> = {}, details: Record<string, string> = {}): Link[] {
  return KEYS.map((key) => ({
    key,
    label: key,
    state: overrides[key] ?? 'ok',
    detail: details[key] ?? 'fine',
    since: null
  }));
}

const word = (links: Link[]) => Object.fromEntries(rows(links).map((r) => [r.key, r.word]));

describe('rows', () => {
  it('everything working is good service on all three rows', () => {
    expect(word(chain())).toEqual({ hotwater: 'Good service', heating: 'Good service', thermostat: 'Good service' });
  });

  it('invariant 14: a dead receiver puts hot water and heating at risk, not the thermostat', () => {
    const links = chain({ receiver: 'down', hotwater: 'unknown', heating: 'unknown' });
    expect(word(links)).toEqual({ hotwater: 'At risk', heating: 'At risk', thermostat: 'Good service' });
  });

  it('invariant 14: losing the internet is "no information", never "at risk"', () => {
    const links = chain({ internet: 'down', hive: 'unknown', hub: 'unknown', receiver: 'unknown' });
    expect(new Set(Object.values(word(links)))).toEqual(new Set(['No information']));
  });

  it('a dead hub puts all three at risk', () => {
    const links = chain({ hub: 'down', receiver: 'unknown', thermostat: 'unknown' });
    expect(word(links)).toEqual({ hotwater: 'At risk', heating: 'At risk', thermostat: 'At risk' });
  });

  it('warnings read in plain words', () => {
    expect(word(chain({ hotwater: 'warn', thermostat: 'warn' }))).toEqual({
      hotwater: 'Switched off',
      heating: 'Good service',
      thermostat: 'Battery low'
    });
  });

  it('before the first check every row says so', () => {
    expect(rows([]).every((r) => r.word === 'No information')).toBe(true);
  });
});

describe('fixes', () => {
  it('invariant 15: only the fault gets a fix line', () => {
    const links = chain({ receiver: 'down', hotwater: 'unknown', heating: 'unknown', thermostat: 'warn' });
    expect(fixes(links, 'receiver').map((f) => f.key)).toEqual(['receiver']);
  });

  it('a lost Hive login points at setup instead of waiting', () => {
    const links = chain({ hive: 'down' }, { hive: 'Hive forgot this Pi and wants an SMS code. Run setup on the Pi.' });
    expect(fixes(links, 'hive')[0].text).toMatch(/hive setup/);
  });

  it('with no fault, each warning gets its line', () => {
    expect(fixes(chain({ hotwater: 'warn' }), null).map((f) => f.key)).toEqual(['hotwater']);
  });
});

describe('worthShowing', () => {
  it('keeps changes into and out of trouble, drops unknown churn', () => {
    expect(worthShowing({ old_state: 'ok', new_state: 'down' })).toBe(true);
    expect(worthShowing({ old_state: 'down', new_state: 'ok' })).toBe(true);
    expect(worthShowing({ old_state: 'ok', new_state: 'unknown' })).toBe(false);
    expect(worthShowing({ old_state: 'unknown', new_state: 'ok' })).toBe(false);
  });
});
