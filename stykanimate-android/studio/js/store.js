// Imported audio files live in IndexedDB so they survive restarts.
const open = () => new Promise((resolve, reject) => {
  const req = indexedDB.open('stykstudio', 1);
  req.onupgradeneeded = () => req.result.createObjectStore('sounds', { keyPath: 'name' });
  req.onsuccess = () => resolve(req.result);
  req.onerror = () => reject(req.error);
});

async function run(mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('sounds', mode);
    const req = fn(tx.objectStore('sounds'));
    tx.oncomplete = () => resolve(req?.result);
    tx.onerror = () => reject(tx.error);
  });
}

export const listSounds = () => run('readonly', (s) => s.getAll());
export const putSound = (name, data) => run('readwrite', (s) => s.put({ name, data }));
