/**
 * LocationDB — IndexedDB-based GPS queue
 * localStorage o'rniga ishlatiladi: xotira saqlash ishonchli, katta hajm, cache tozalashda yo'qolmaydi.
 */

const LocationDB = (() => {
    const DB_NAME    = 'stockfirm_location_db';
    const DB_VERSION = 1;
    const STORE_NAME = 'location_queue';
    const MAX_POINTS = 2000;
    const MAX_AGE_MS = 24 * 60 * 60 * 1000; // 24 soat — eskiroq nuqtalar tozalanadi

    let _db = null;

    function open() {
        if (_db) return Promise.resolve(_db);
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);

            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE_NAME)) {
                    const store = db.createObjectStore(STORE_NAME, {
                        keyPath: 'id',
                        autoIncrement: true
                    });
                    store.createIndex('by_ts', 'client_timestamp', { unique: false });
                }
            };

            req.onsuccess = (e) => {
                _db = e.target.result;
                _db.onversionchange = () => { _db.close(); _db = null; };
                resolve(_db);
            };

            req.onerror = () => reject(req.error);
        });
    }

    function tx(mode) {
        return open().then(db => {
            const t = db.transaction(STORE_NAME, mode);
            const s = t.objectStore(STORE_NAME);
            return { t, s };
        });
    }

    function req2p(r) {
        return new Promise((res, rej) => {
            r.onsuccess = () => res(r.result);
            r.onerror   = () => rej(r.error);
        });
    }

    /** Yangi nuqta qo'shish */
    async function enqueue(point) {
        const { s } = await tx('readwrite');
        await req2p(s.add({ ...point, queued_at: Date.now(), retry_count: 0 }));
        await _purgeOld();
        await _trimOverflow();
    }

    /** N ta nuqtani olish (o'chirmasdan) */
    async function peek(n = 100) {
        const { s } = await tx('readonly');
        return new Promise((resolve, reject) => {
            const results = [];
            const cursor = s.openCursor();
            cursor.onsuccess = (e) => {
                const c = e.target.result;
                if (!c || results.length >= n) return resolve(results);
                results.push(c.value);
                c.continue();
            };
            cursor.onerror = () => reject(cursor.error);
        });
    }

    /** Muvaffaqiyatli yuborilgan nuqtalarni o'chirish (id bo'yicha) */
    async function dequeue(ids) {
        if (!ids || ids.length === 0) return;
        const { s } = await tx('readwrite');
        await Promise.all(ids.map(id => req2p(s.delete(id))));
    }

    /** Retry count ni oshirish */
    async function incrementRetry(ids) {
        if (!ids || ids.length === 0) return;
        const { s } = await tx('readwrite');
        for (const id of ids) {
            const point = await req2p(s.get(id));
            if (point) {
                point.retry_count = (point.retry_count || 0) + 1;
                await req2p(s.put(point));
            }
        }
    }

    /** Umumiy queue hajmi */
    async function count() {
        const { s } = await tx('readonly');
        return req2p(s.count());
    }

    /** Oxirgi muvaffaqiyatli sync vaqti (localStorage dan) */
    function getLastSync() {
        return localStorage.getItem('sf_last_sync') || null;
    }

    function setLastSync() {
        localStorage.setItem('sf_last_sync', new Date().toISOString());
    }

    /** 24 soatdan eski nuqtalarni tozalash */
    async function _purgeOld() {
        const cutoff = new Date(Date.now() - MAX_AGE_MS).toISOString();
        const { s } = await tx('readwrite');
        const idx = s.index('by_ts');
        const range = IDBKeyRange.upperBound(cutoff);
        return new Promise((resolve) => {
            const cursor = idx.openCursor(range);
            cursor.onsuccess = (e) => {
                const c = e.target.result;
                if (!c) return resolve();
                c.delete();
                c.continue();
            };
            cursor.onerror = () => resolve();
        });
    }

    /** MAX_POINTS dan oshsa eng eski nuqtalarni o'chirish */
    async function _trimOverflow() {
        const total = await count();
        if (total <= MAX_POINTS) return;
        const excess = total - MAX_POINTS;
        const { s } = await tx('readwrite');
        return new Promise((resolve) => {
            let deleted = 0;
            const cursor = s.openCursor();
            cursor.onsuccess = (e) => {
                const c = e.target.result;
                if (!c || deleted >= excess) return resolve();
                c.delete();
                deleted++;
                c.continue();
            };
            cursor.onerror = () => resolve();
        });
    }

    return { enqueue, peek, dequeue, incrementRetry, count, getLastSync, setLastSync, open };
})();
