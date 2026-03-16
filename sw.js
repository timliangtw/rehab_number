const CACHE_NAME = 'grid-rehab-v1';
const URLS_TO_CACHE = [
    './',
    './index.html',
    './styles.css',
    './main.py',
    './manifest.json',
    './icon-192.png',
    './icon-512.png',
    './flower.png'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(URLS_TO_CACHE))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(name => name !== CACHE_NAME)
                    .map(name => caches.delete(name))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request).then(
                    function (response) {
                        // Check if we received a valid response
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            // Cache external dependencies like pyscript / pyodide lazily
                            if (event.request.url.includes('pyscript') || event.request.url.includes('pyodide')) {
                                var responseToCache = response.clone();
                                caches.open(CACHE_NAME).then(function (cache) {
                                    cache.put(event.request, responseToCache);
                                });
                            }
                            return response;
                        }
                        // Cache valid local resources
                        var responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then(function (cache) {
                                cache.put(event.request, responseToCache);
                            });
                        return response;
                    }
                ).catch(() => {
                    // Offline fallback if needed
                });
            })
    );
});
