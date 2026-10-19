/** Compatibility for browser data saved by earlier releases. New writes use ZhangWen names. */
export function migrateBrowserNames(provided?: Storage): void {
  try {
    const storage = provided ?? localStorage;
    const keys = Array.from({ length: storage.length }, (_, i) => storage.key(i)).filter((key): key is string => key?.startsWith('mu-') ?? false);
    for (const old of keys) {
      const current = 'zhangwen-' + old.slice(3), value = storage.getItem(old);
      if (value === null) continue;
      try {
        if (storage.getItem(current) === null) storage.setItem(current, value);
        // A quota error or conflicting newer draft must leave the old copy intact.
        if (storage.getItem(current) === value) storage.removeItem(old);
      } catch { /* Keep the old value for a future retry. */ }
    }
  } catch { /* Browser storage can be unavailable; the workbench still opens. */ }
}

const previousDatabases: Record<string, string> = {
  'zhangwen-project-folders': 'mu-project-folders',
  'zhangwen-firmware-backups': 'mu-firmware-backups',
};
const migrations = new Map<string, Promise<void>>();

async function copyPreviousDatabase(db: IDBDatabase, previous: string, store: string, keyPath: string): Promise<void> {
  const old = await new Promise<IDBDatabase | null>((resolve, reject) => {
    const request = indexedDB.open(previous); let absent = false;
    request.onupgradeneeded = () => { absent = true; request.transaction?.abort(); };
    request.onsuccess = () => resolve(request.result);
    request.onerror = event => { event.preventDefault(); if (absent) resolve(null); else reject(new Error('无法读取旧版浏览器资料，原记录已保留，请刷新后重试。')); };
  });
  if (!old) return;
  try {
    if (!old.objectStoreNames.contains(store)) return;
    const records = await new Promise<{ values: unknown[]; keys: IDBValidKey[] }>((resolve, reject) => {
      const tx = old.transaction(store), objectStore = tx.objectStore(store);
      if (objectStore.keyPath !== keyPath) { tx.abort(); reject(new Error('旧版浏览器资料结构不符，原记录已保留。')); return; }
      const values = objectStore.getAll(), keys = objectStore.getAllKeys();
      tx.oncomplete = () => resolve({ values: values.result as unknown[], keys: keys.result });
      tx.onerror = tx.onabort = () => reject(new Error('无法读取旧版浏览器资料，原记录已保留。'));
    });
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(store, 'readwrite'), objectStore = tx.objectStore(store);
      records.keys.forEach((key, i) => {
        const request = objectStore.getKey(key);
        request.onsuccess = () => { if (request.result === undefined) objectStore.put(records.values[i]); };
      });
      tx.oncomplete = () => resolve();
      tx.onerror = tx.onabort = () => reject(new Error('浏览器资料迁移未完成，旧版记录已保留，请刷新后重试。'));
    });
  } finally { old.close(); }
}

export async function openPlatformDatabase(name: string, store: string, keyPath: string): Promise<IDBDatabase> {
  const db = await new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open(name, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(store, { keyPath });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('浏览器无法保存本地资料，请检查存储权限。'));
  });
  try {
    const previous = previousDatabases[name];
    if (previous && !migrations.has(name)) migrations.set(name, copyPreviousDatabase(db, previous, store, keyPath));
    await migrations.get(name);
    return db;
  } catch (error) { db.close(); migrations.delete(name); throw error; }
}

export async function lockProjectFolder<T>(portableId: string, task: () => Promise<T>): Promise<T> {
  if (!navigator.locks) return task();
  // Old and refreshed tabs serialize on the same project while the rollout completes.
  return navigator.locks.request('mu-project-folder-' + portableId,
    () => navigator.locks.request('zhangwen-project-folder-' + portableId, task));
}
