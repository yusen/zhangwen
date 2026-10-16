import type { ProjectSnapshot } from '../../../packages/contracts/src/mu';
import { sha256 } from './serial';

export const PROJECT_FILE = 'zhangwen.project.json';
const MAX_BYTES = 32 * 1024 * 1024;
export type ProjectDirectory = FileSystemDirectoryHandle & {
  queryPermission?: (options: { mode: 'readwrite' }) => Promise<PermissionState>;
  requestPermission?: (options: { mode: 'readwrite' }) => Promise<PermissionState>;
};
export interface FolderBinding {
  projectId: string; handle: ProjectDirectory; checkpointHash: string | null; mainHash: string | null;
}
interface PickerWindow extends Window {
  showDirectoryPicker?: (options: { id: string; mode: 'readwrite' }) => Promise<ProjectDirectory>;
}
const hash = (text: string) => sha256(new TextEncoder().encode(text));
export function pickProjectDirectory(): Promise<ProjectDirectory> {
  const picker = (window as PickerWindow).showDirectoryPicker;
  if (!picker) return Promise.reject(new Error('选择项目文件夹需要桌面 Chrome/Edge，并通过本机地址打开。'));
  return picker.call(window, { id: 'zhangwen-project', mode: 'readwrite' });
}
export function pickerCancelled(error: unknown): boolean { return error instanceof DOMException && error.name === 'AbortError'; }
async function read(handle: ProjectDirectory, name: string, limit = MAX_BYTES): Promise<string | null> {
  try {
    const file = await (await handle.getFileHandle(name)).getFile();
    if (file.size > limit) throw new Error(`${name} 超过大小限制，未读取或覆盖。`);
    return await file.text();
  } catch (error) {
    if (error instanceof DOMException && error.name === 'NotFoundError') return null;
    throw error;
  }
}
export async function prepareNewDirectory(handle: ProjectDirectory): Promise<void> {
  if (await read(handle, PROJECT_FILE) !== null) throw new Error('此文件夹已有掌问项目，请通过「加载」打开，或选择新的项目文件夹。');
  if (await read(handle, 'main.py', 65_536) !== null) throw new Error('此文件夹已有 main.py。为保留原文件，请为新项目选择另一个文件夹。');
}
export async function readProjectDirectory(handle: ProjectDirectory): Promise<{ snapshot: ProjectSnapshot; binding: FolderBinding; externalCode: string | null }> {
  const raw = await read(handle, PROJECT_FILE);
  if (raw === null) throw new Error('所选文件夹没有 zhangwen.project.json，请选择掌问项目文件夹。');
  let snapshot: ProjectSnapshot;
  try { snapshot = JSON.parse(raw) as ProjectSnapshot; } catch { throw new Error('项目快照不是有效 JSON，未修改文件或当前项目。'); }
  if (snapshot?.format !== 'zhangwen-project' || snapshot.schemaVersion !== 1) throw new Error('不支持此项目格式或版本。');
  // The service performs full schema and checksum validation before import.
  const main = await read(handle, 'main.py', 65_536);
  const current = Array.isArray(snapshot.versions) ? snapshot.versions.find(item => item.revision === snapshot.project?.revision) : undefined;
  const externalCode = main !== null && current && main !== current.code ? main : null;
  if (externalCode?.includes('\0')) throw new Error('main.py 包含 NUL，无法作为代码草稿载入。');
  return { snapshot, externalCode, binding: { projectId: '', handle, checkpointHash: await hash(raw), mainHash: main === null ? null : await hash(main) } };
}
export async function ensureFolderPermission(binding: FolderBinding, request = false): Promise<void> {
  if (!binding.handle.queryPermission || await binding.handle.queryPermission({ mode: 'readwrite' }) === 'granted') return;
  if (request && binding.handle.requestPermission && await binding.handle.requestPermission({ mode: 'readwrite' }) === 'granted') return;
  throw new Error('项目文件夹尚未获得写入权限。点击「保存」重新授权；本机对话与版本仍保留。');
}
async function write(handle: ProjectDirectory, name: string, data: string): Promise<void> {
  const stream = await (await handle.getFileHandle(name, { create: true })).createWritable();
  try { await stream.write(data); await stream.close(); }
  catch (error) { await stream.abort().catch(() => {}); throw error; }
}
export async function writeProjectDirectory(binding: FolderBinding, snapshot: ProjectSnapshot): Promise<void> {
  const task = async () => {
    await ensureFolderPermission(binding);
    const raw = await read(binding.handle, PROJECT_FILE), main = await read(binding.handle, 'main.py', 65_536);
    if ((raw === null ? null : await hash(raw)) !== binding.checkpointHash || (main === null ? null : await hash(main)) !== binding.mainHash) {
      throw new Error('项目文件夹已被其他页面或编辑器修改。未覆盖磁盘文件；请重新加载该文件夹，或选择另一个文件夹另存。');
    }
    const current = snapshot.versions.find(item => item.revision === snapshot.project.revision);
    if (!current || current.source === 'ai') throw new Error('项目缺少当前已保存代码，未写文件夹。');
    const json = JSON.stringify(snapshot, null, 2) + '\n';
    if (new TextEncoder().encode(json).length > MAX_BYTES) throw new Error('项目快照超过32MiB，未截断或覆盖。');
    if (main !== current.code) {
      await write(binding.handle, 'main.py', current.code);
      binding.mainHash = await hash(current.code);
    }
    // Immutable CAD files remain visible alongside the portable checkpoint.
    // Every path is validated again here before browser-authorized folder I/O.
    if (snapshot.structure?.assets) {
      const root = await binding.handle.getDirectoryHandle('structure', { create: true });
      for (const [key, asset] of Object.entries(snapshot.structure.assets)) {
        const parts = key.split('/');
        if (parts.length < 3 || parts.length > 4 || !/^[a-f0-9]{32}$/.test(parts[0]) || !/^ZW-PRODUCT-\d{8}-\d{6}(?:-\d{2})?$/.test(parts[1]) || parts.slice(2).some(p => !/^[a-zA-Z0-9_.-]+$/.test(p) || p === '.' || p === '..')) throw new Error('结构资产路径无效，未覆盖文件夹快照。');
        const bytes = Uint8Array.from(atob(asset.content), char => char.charCodeAt(0));
        if (await sha256(bytes) !== asset.sha256) throw new Error('结构文件校验失败，未覆盖项目快照。');
        let directory = root;
        for (const part of parts.slice(0, -1)) directory = await directory.getDirectoryHandle(part, { create: true });
        const name = parts.at(-1)!;
        let existing: FileSystemFileHandle | null = null;
        try { existing = await directory.getFileHandle(name); } catch (e) { if (!(e instanceof DOMException && e.name === 'NotFoundError')) throw e; }
        if (existing) {
          const previous = new Uint8Array(await (await existing.getFile()).arrayBuffer());
          if (await sha256(previous) !== asset.sha256) throw new Error(`结构文件 ${name} 已被外部修改，未覆盖。`);
        } else {
          const handle = await directory.getFileHandle(name, { create: true });
          const writer = await handle.createWritable();
          try { await writer.write(bytes); await writer.close(); }
          catch (e) { await writer.abort().catch(() => {}); throw e; }
        }
        const check = new Uint8Array(await (await (await directory.getFileHandle(name)).getFile()).arrayBuffer());
        if (await sha256(check) !== asset.sha256) throw new Error(`结构文件 ${name} 回读不一致，未覆盖项目快照。`);
      }
    }
    await write(binding.handle, PROJECT_FILE, json);
    binding.checkpointHash = await hash(json);
    await rememberFolder(binding);
  };
  // Serializes folder checkpoints across tabs; fingerprints also reject stale writers.
  if (navigator.locks) await navigator.locks.request('mu-project-folder-' + snapshot.portableId, task);
  else await task();
}

function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('mu-project-folders', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('folders', { keyPath: 'projectId' });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error('浏览器无法保存项目文件夹关联，请重新选择文件夹。'));
  });
}
export async function rememberFolder(binding: FolderBinding): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction('folders', 'readwrite'); tx.objectStore('folders').put(binding);
      tx.oncomplete = () => resolve(); tx.onerror = tx.onabort = () => reject(new Error('文件已保存，但浏览器无法记住文件夹；刷新后需重新选择。'));
    });
  } finally { db.close(); }
}
export async function recallFolder(projectId: string): Promise<FolderBinding | null> {
  const db = await database();
  try {
    return await new Promise<FolderBinding | null>((resolve, reject) => {
      const request = db.transaction('folders').objectStore('folders').get(projectId);
      request.onsuccess = () => resolve((request.result as FolderBinding | undefined) ?? null);
      request.onerror = () => reject(new Error('无法读取项目文件夹关联，请重新加载项目文件夹。'));
    });
  } finally { db.close(); }
}
