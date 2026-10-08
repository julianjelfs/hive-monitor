export type LinkState = 'ok' | 'warn' | 'down' | 'unknown';

export interface Link {
  key: string;
  label: string;
  state: LinkState;
  detail: string;
  // Hot water and heating only: running now. Null when it has no on/off or we can't see it.
  active: boolean | null;
  since: string | null;
}

export interface Event {
  at: string;
  link: string;
  label: string;
  old_state: LinkState;
  new_state: LinkState;
  detail: string;
  alert: 'down' | 'recovered' | null;
}

export interface Status {
  checked_at: string | null;
  interval: number;
  links: Link[];
  fault: string | null;
  push_configured: boolean;
  events: Event[];
}

export type HistoryEntry =
  | {
      at: string;
      kind: 'state';
      old_state: LinkState;
      new_state: LinkState;
      detail: string;
      alert: 'down' | 'recovered' | null;
    }
  | { at: string; kind: 'activity'; active: boolean }
  // One field Hive reports, as JSON text. old is null the first time it's seen.
  | { at: string; kind: 'reading'; path: string; old: string | null; new: string };

export interface History {
  key: string;
  label: string;
  entries: HistoryEntry[]; // newest first
}

export async function getHistory(key: string): Promise<History> {
  const response = await fetch(`/api/links/${encodeURIComponent(key)}/history`);
  if (!response.ok) throw new Error(`history ${response.status}`);
  return response.json();
}

export async function getStatus(): Promise<Status> {
  const response = await fetch('/api/status');
  if (!response.ok) throw new Error(`status ${response.status}`);
  return response.json();
}

export async function checkNow(): Promise<void> {
  await fetch('/api/check', { method: 'POST' });
}

export async function testPush(): Promise<string> {
  const response = await fetch('/api/test-push', { method: 'POST' });
  if (response.ok) return 'Sent. Check your phone.';
  const body = await response.json().catch(() => ({}));
  return body.detail ?? `Failed (${response.status})`;
}
