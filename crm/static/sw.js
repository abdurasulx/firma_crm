/**
 * StockFirm Service Worker
 * - GPS batch sync (Background Sync API)
 * - Xarita tile cache (cache-first)
 * - Statik resurslar cache
 * - Offline fallback
 */

const CACHE_VERSION   = 'sf-v1';
const TILE_CACHE      = 'sf-tiles-v1';
const STATIC_CACHE    = 'sf-static-v1';
const SYNC_TAG        = 'sf-location-sync';
const MAX_TILE_AGE_MS = 7 * 24 * 60 * 60 * 1000; // 7 kun

const PRECACHE_URLS = [
    '/offline/',
    '/static/js/location-db.js',
    '/static/js/main.js',
];

const TILE_HOSTS = [
    'cartodb-basemaps-a.global.ssl.fastly.net',
    'cartodb-basemaps-b.global.ssl.fastly.net',
    'cartodb-basemaps-c.global.ssl.fastly.net',
    'cartodb-basemaps-d.global.ssl.fastly.net',
    'tile.openstreetmap.org',
    'a.tile.openstreetmap.org',
    'b.tile.openstreetmap.org',
    'c.tile.openstreetmap.org',
];

// ─── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => cache.addAll(PRECACHE_URLS).catch(() => {}))
            .then(() => self.skipWaiting())
    );
});

// ─── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys
                    .filter(k => k !== TILE_CACHE && k !== STATIC_CACHE)
                    .map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// ─── Fetch ────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // 1. Xarita tile lari — cache-first (7 kun saqlash)
    if (TILE_HOSTS.includes(url.hostname)) {
        event.respondWith(tileStrategy(event.request));
        return;
    }

    // 2. GPS batch API — network-only (POST), offline bo'lsa queue ga yoz
    if (url.pathname.includes('/api/location/batch/')) {
        // SW intercepti yo'q — Background Sync orqali boshqariladi
        return;
    }

    // 3. Static fayllar — cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(staticStrategy(event.request));
        return;
    }

    // 4. Navigation (HTML sahifalar) — network-first, offline bo'lsa fallback
    if (event.request.mode === 'navigate') {
        event.respondWith(navigationStrategy(event.request));
        return;
    }
});

// ─── Tile cache strategy ──────────────────────────────────────────────────────
async function tileStrategy(request) {
    const cache = await caches.open(TILE_CACHE);
    const cached = await cache.match(request);

    if (cached) {
        const dateHeader = cached.headers.get('sf-cached-at');
        const age = Date.now() - (dateHeader ? parseInt(dateHeader) : 0);
        if (age < MAX_TILE_AGE_MS) return cached;
    }

    try {
        const fresh = await fetch(request.clone());
        if (fresh.ok) {
            // Kesh vaqtini saqlash uchun yangi header qo'shamiz
            const headers = new Headers(fresh.headers);
            headers.set('sf-cached-at', String(Date.now()));
            const toCache = new Response(await fresh.clone().arrayBuffer(), {
                status: fresh.status,
                statusText: fresh.statusText,
                headers,
            });
            cache.put(request, toCache);
        }
        return fresh;
    } catch {
        if (cached) return cached;
        return new Response('', { status: 503 });
    }
}

// ─── Static strategy ──────────────────────────────────────────────────────────
async function staticStrategy(request) {
    const cache = await caches.open(STATIC_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;

    try {
        const fresh = await fetch(request);
        if (fresh.ok) cache.put(request, fresh.clone());
        return fresh;
    } catch {
        return new Response('', { status: 503 });
    }
}

// ─── Navigation strategy ──────────────────────────────────────────────────────
async function navigationStrategy(request) {
    try {
        const fresh = await fetch(request);
        return fresh;
    } catch {
        const cache = await caches.open(STATIC_CACHE);
        const fallback = await cache.match('/offline/');
        return fallback || new Response('<h1>Offline</h1>', {
            headers: { 'Content-Type': 'text/html' }
        });
    }
}

// ─── Background Sync ──────────────────────────────────────────────────────────
self.addEventListener('sync', (event) => {
    if (event.tag === SYNC_TAG) {
        event.waitUntil(syncLocations());
    }
});

async function syncLocations() {
    // SW da IndexedDB ga murojaat qilamiz
    const db = await openLocationDB();
    const points = await peekQueue(db, 100);
    if (points.length === 0) return;

    const ids = points.map(p => p.id);
    const clean = points.map(({ id, queued_at, retry_count, ...p }) => p);

    try {
        const response = await fetch('/api/location/batch/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ points: clean }),
            credentials: 'include',
        });

        if (response.ok) {
            await dequeuePoints(db, ids);
            // Keyingi batch bormi?
            const remaining = await countQueue(db);
            if (remaining > 0) {
                // Recursive — barcha queue yuborilguncha
                await syncLocations();
            }
        } else if (response.status >= 500) {
            throw new Error('server_error');
        }
        // 4xx — ma'lumot noto'g'ri, o'chirib tashlaymiz
        else {
            await dequeuePoints(db, ids);
        }
    } catch {
        // Network xatosi — BackgroundSync qayta urinadi
        throw new Error('sync_failed');
    }
}

// ─── SW ichida IndexedDB helpers ──────────────────────────────────────────────
function openLocationDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open('stockfirm_location_db', 1);
        req.onsuccess  = e => resolve(e.target.result);
        req.onerror    = () => reject(req.error);
        req.onupgradeneeded = e => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains('location_queue')) {
                const store = db.createObjectStore('location_queue', { keyPath: 'id', autoIncrement: true });
                store.createIndex('by_ts', 'client_timestamp', { unique: false });
            }
        };
    });
}

function peekQueue(db, n) {
    return new Promise((resolve, reject) => {
        const results = [];
        const cursor = db.transaction('location_queue', 'readonly')
                         .objectStore('location_queue')
                         .openCursor();
        cursor.onsuccess = e => {
            const c = e.target.result;
            if (!c || results.length >= n) return resolve(results);
            results.push(c.value);
            c.continue();
        };
        cursor.onerror = () => reject(cursor.error);
    });
}

function dequeuePoints(db, ids) {
    const store = db.transaction('location_queue', 'readwrite').objectStore('location_queue');
    return Promise.all(ids.map(id =>
        new Promise((res, rej) => {
            const r = store.delete(id);
            r.onsuccess = res;
            r.onerror   = rej;
        })
    ));
}

function countQueue(db) {
    return new Promise((resolve, reject) => {
        const r = db.transaction('location_queue', 'readonly')
                    .objectStore('location_queue')
                    .count();
        r.onsuccess = () => resolve(r.result);
        r.onerror   = () => reject(r.error);
    });
}

// ─── SW ↔ Client xabarlashuv ──────────────────────────────────────────────────
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
    if (event.data?.type === 'GET_VERSION') {
        event.ports[0]?.postMessage({ version: CACHE_VERSION });
    }
});
