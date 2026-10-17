// Keeps the page itself loadable when the Pi can't be reached, so the app opens and says
// "Can't reach the monitor" instead of showing the browser's error page.
// Status (/api) is never cached: a stale "everything's working" would be worse than none.
const CACHE = 'hive-shell-v1';

// Off the wifi and the tailnet, the Pi's address can hang instead of failing. Give up after
// this long and use the cached page.
const NETWORK_TIMEOUT_MS = 4000;
// After a miss, skip the network for a while so every request doesn't wait for another failure.
const UNREACHABLE_FOR_MS = 30_000;
let unreachableUntil = 0;

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
	event.waitUntil(
		caches
			.keys()
			.then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
			.then(() => self.clients.claim())
	);
});

self.addEventListener('fetch', (event) => {
	const url = new URL(event.request.url);
	if (event.request.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) {
		return;
	}
	// Network first, so a rebuild shows up straight away; the cache is only the fallback.
	event.respondWith(
		network(event.request)
			.then((response) => {
				if (response.ok) {
					const copy = response.clone();
					caches.open(CACHE).then((cache) => cache.put(event.request, copy));
				}
				return response;
			})
			.catch(() =>
				caches
					.match(event.request)
					.then((hit) => hit || (event.request.mode === 'navigate' ? caches.match('/') : undefined))
					.then((hit) => hit || Response.error())
			)
	);
});

// The Pi's response, or a rejection if it can't be reached in time. A gateway error counts as
// unreachable: that is Caddy answering for an app that is down or restarting.
function network(request) {
	if (Date.now() < unreachableUntil) return Promise.reject(new Error('unreachable'));
	// A race rather than an AbortSignal: fetch() refuses any options alongside a navigation request.
	const timeout = new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), NETWORK_TIMEOUT_MS));
	return Promise.race([fetch(request), timeout])
		.then((response) => {
			if (response.status >= 502 && response.status <= 504) throw new Error('gateway');
			return response;
		})
		.catch((error) => {
			unreachableUntil = Date.now() + UNREACHABLE_FOR_MS;
			throw error;
		});
}
