import type { DeviceIdentity } from '../../../packages/contracts/src/platform';

/** Browser-local backups survive tab refresh. Never upload device identities to API. */
export interface DeviceBackup { id: string; path: string; bytes: Uint8Array | null; identity: DeviceIdentity; createdAt: string }
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('zhangwen-device-backups', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('backups', { keyPath: 'id' });
    request.onerror = () => reject(new Error('浏览器备份存储不可用；未开始上传。'));
    request.onsuccess = () => resolve(request.result);
  });
}
export async function persistBackup(data: Omit<DeviceBackup, 'id' | 'createdAt'>): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('backups', 'readwrite');
      tx.objectStore('backups').add({ ...data, id: crypto.randomUUID(), createdAt: new Date().toISOString() });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(new Error('设备备份保存失败（可能存储空间不足）；未开始上传。'));
      tx.onabort = () => reject(new Error('设备备份保存中断；未开始上传。'));
    });
  } finally { db.close(); }
}
export async function latestBackup(): Promise<DeviceBackup | undefined> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const request = db.transaction('backups', 'readonly').objectStore('backups').getAll();
      request.onsuccess = () => resolve((request.result as DeviceBackup[]).sort((a, b) => b.createdAt.localeCompare(a.createdAt))[0]);
      request.onerror = () => reject(new Error('无法读取设备备份。'));
    });
  } finally { db.close(); }
}
