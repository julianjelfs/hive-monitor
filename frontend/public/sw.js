// Keeps the page itself loadable when the Pi can't be reached, so the app opens and says
// "Can't reach the monitor" instead of showing the browser's error page.
// Status (/api) is never cached: a stale "everything's working" would be worse than none.
const CACHE = 'hive-shell-v1';

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
		fetch(event.request)
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
