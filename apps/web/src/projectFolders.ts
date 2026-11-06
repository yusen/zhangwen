import type { ProjectSnapshot, HardwareResourceBundle } from '../../../packages/contracts/src/platform';
import { openPlatformDatabase, lockProjectFolder } from './legacyBrowserNames';
import { sha256 } from './serial';
import { projectFolderFiles, hardwareFolderFiles } from './projectFolderLayout';
import { api } from './api';
import { workflowFolderFiles } from './workflowUtils';
import type { ManagedProjectFolder, ManagedFolderFile } from '../../../packages/contracts/src/projectFolder';

export const PROJECT_FILE = 'zhangwen.project.json';
const MAX_BYTES = 32 * 1024 * 1024;
export type ProjectDirectory = FileSystemDirectoryHandle & {
  queryPermission?: (options: { mode: 'readwrite' }) => Promise<PermissionState>;
  requestPermission?: (options: { mode: 'readwrite' }) => Promise<PermissionState>;
};
export interface FolderBinding {
  projectId: string; handle: ProjectDirectory; checkpointHash: string | null; mainHash: string | null;
  /** Local-only convenience, never included in a portable snapshot. */
  nativePath?: string;
  managed?: boolean;
  nativeCheckpointHash?: string | null;
}

async function managedBinding(projectId:string,info:ManagedProjectFolder,previous?:FolderBinding):Promise<FolderBinding>{
  const handle=previous?.handle??await(await navigator.storage.getDirectory()).getDirectoryHandle('zhangwen-'+projectId,{create:true});
  return {projectId,handle,managed:true,nativePath:info.path,nativeCheckpointHash:info.checkpointHash,
    checkpointHash:previous?.checkpointHash??null,mainHash:previous?.mainHash??null};
}
export async function createManagedFolder(projectId:string):Promise<FolderBinding>{
  const info=await api<ManagedProjectFolder>(`/projects/${projectId}/folder/managed`,'POST',{});
  const binding=await managedBinding(projectId,info);await rememberFolder(binding);return binding;
}
export async function openProjectFolder(binding:FolderBinding):Promise<void>{
  if(binding.managed){await api(`/projects/${binding.projectId}/folder/managed/open`,'POST',{});return;}
  if(!binding.checkpointHash)throw new Error('请先保存项目，再打开文件夹。');
  const result=await api<{status:string;path?:string}>(`/projects/${binding.projectId}/folder/open`,'POST',{checkpointHash:binding.checkpointHash,...(binding.nativePath?{path:binding.nativePath}:{})});
  if(result.path){binding.nativePath=result.path;await rememberFolder(binding);}
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
  if (await read(handle, PROJECT_FILE) !== null) throw new Error('此文件夹已有掌问项目，请通过「项目→打开项目」打开，或选择新的项目文件夹。');
  if (await read(handle, 'main.py', 65_536) !== null) throw new Error('此文件夹已有 main.py。为保留原文件，请为新项目选择另一个文件夹。');
  if (await read(handle, 'chat-task.txt', 65_536) !== null) throw new Error('此文件夹已有 chat-task.txt，请选择新的项目文件夹。');
}
export async function readProjectDirectory(handle: ProjectDirectory): Promise<{ snapshot: ProjectSnapshot; binding: FolderBinding; externalCode: string | null }> {
  const raw = await read(handle, PROJECT_FILE);
  if (raw === null) throw new Error('所选文件夹没有 zhangwen.project.json，请选择掌问项目文件夹。');
  let snapshot: ProjectSnapshot;
  try { snapshot = JSON.parse(raw) as ProjectSnapshot; } catch { throw new Error('项目项目备份不是有效 JSON，未修改文件或当前项目。'); }
  if (snapshot?.format !== 'zhangwen-project' || snapshot.schemaVersion !== 1) throw new Error('不支持此项目格式或版本。');
  // The service performs full schema and checksum validation before import.
  const main = await read(handle, snapshot.project?.programmingMode === 'chat-coding' ? 'chat-task.txt' : 'main.py', 65_536);
  const current = Array.isArray(snapshot.versions) ? snapshot.versions.find(item => item.revision === snapshot.project?.revision) : undefined;
  const externalCode = main !== null && current && main !== current.code ? main : null;
  if (externalCode?.includes('\0')) throw new Error('任务或程序文件包含 NUL，无法作为草稿载入。');
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
async function writeImmutableFile(root: ProjectDirectory, path: string[], bytes: Uint8Array<ArrayBuffer>, checksum: string): Promise<void> {
  let directory: FileSystemDirectoryHandle = root;
  for (const part of path.slice(0, -1)) directory = await directory.getDirectoryHandle(part, { create: true });
  const name = path.at(-1)!, label = path.join('/');
  let existing: FileSystemFileHandle | null = null;
  try { existing = await directory.getFileHandle(name); }
  catch (error) { if (!(error instanceof DOMException && error.name === 'NotFoundError')) throw error; }
  if (existing) {
    const previous = await existing.getFile();
    if (previous.size !== bytes.byteLength || await sha256(new Uint8Array(await previous.arrayBuffer())) !== checksum) {
      throw new Error(`文件 ${label} 已被外部修改，未覆盖。`);
    }
  } else {
    const handle = await directory.getFileHandle(name, { create: true });
    let writer: FileSystemWritableFileStream | null = null;
    try { writer = await handle.createWritable(); await writer.write(bytes); await writer.close(); }
    catch (error) {
      await writer?.abort().catch(() => {});
      // Only discard the empty file just created by this failed attempt. Never
      // remove a pre-existing file or any bytes that appeared in the meantime.
      try {
        const pending = await directory.getFileHandle(name);
        if (await pending.isSameEntry(handle) && (await pending.getFile()).size === 0) await directory.removeEntry(name);
      } catch { /* A later retry still reports any remaining conflict. */ }
      throw error;
    }
  }
  const check = new Uint8Array(await (await (await directory.getFileHandle(name)).getFile()).arrayBuffer());
  if (await sha256(check) !== checksum) throw new Error(`文件 ${label} 回读不一致，未覆盖项目项目备份。`);
}
export async function writeProjectDirectory(binding: FolderBinding, snapshot: ProjectSnapshot): Promise<void> {
  const task = async () => {
    await ensureFolderPermission(binding);
    const primaryFile = snapshot.project.programmingMode === 'chat-coding' ? 'chat-task.txt' : 'main.py';
    const raw = await read(binding.handle, PROJECT_FILE), main = await read(binding.handle, primaryFile, 65_536);
    const previousPrimary=raw&&JSON.parse(raw).project?.programmingMode==='chat-coding'?'chat-task.txt':'main.py';
    const previousMain=previousPrimary===primaryFile?main:await read(binding.handle,previousPrimary,65_536);
    if ((raw === null ? null : await hash(raw)) !== binding.checkpointHash || (previousMain === null ? null : await hash(previousMain)) !== binding.mainHash || previousPrimary!==primaryFile&&main!==null) {
      throw new Error('项目文件夹已被其他页面或编辑器修改。未覆盖磁盘文件；请重新加载该文件夹，或选择另一个文件夹另存。');
    }
    const current = snapshot.versions.find(item => item.revision === snapshot.project.revision);
    if (!current || current.source === 'ai') throw new Error('项目缺少当前已保存代码，未写文件夹。');
    const json = JSON.stringify(snapshot, null, 2) + '\n';
    if (new TextEncoder().encode(json).length > MAX_BYTES) throw new Error('项目项目备份超过32MiB，未截断或覆盖。');
    // Validate all source paths and bytes before changing the folder. Internal job IDs
    // stay in the checkpoint; visible copies are grouped by purpose and version.
    const resources = await api<HardwareResourceBundle>(`/projects/${binding.projectId}/hardware-resources?expectedRevision=${snapshot.project.revision}`);
    const decoded = new Map<string, Promise<{ bytes: Uint8Array<ArrayBuffer>; checksum: string }>>();
    const learningFiles = await workflowFolderFiles(snapshot.project.name, snapshot.workflow);
    const files = await Promise.all([...projectFolderFiles(snapshot), ...hardwareFolderFiles(resources), ...learningFiles].map(async file => {
      const source = 'text' in file.data ? 'text:' + file.data.text : 'base64:' + file.data.base64;
      let pending = decoded.get(source);
      if (!pending) {
        const bytes = 'text' in file.data ? new TextEncoder().encode(file.data.text) :
          Uint8Array.from(atob(file.data.base64), char => char.charCodeAt(0));
        pending = sha256(bytes).then(checksum => ({ bytes, checksum })); decoded.set(source, pending);
      }
      const { bytes, checksum } = await pending;
      if (checksum !== file.sha256) throw new Error('项目历史文件校验失败，未覆盖文件夹项目备份。');
      return { ...file, bytes };
    }));
    const referenceFiles = (await Promise.all((snapshot.references ?? []).map(async item => {
      if (!/^ref_[a-f0-9]{32}$/.test(item.id) || !Number.isSafeInteger(item.version) || item.version < 1 ||
          item.name.split('/').some(part => !part || part === '.' || part === '..' || /[\\<>:"|?*\x00-\x1f]/.test(part))) {
        throw new Error('项目资料路径无效，未写入文件夹。');
      }
      const bytes = item.encoding === 'text' ? new TextEncoder().encode(item.original) : Uint8Array.from(atob(item.original), c => c.charCodeAt(0));
      const checksum=await sha256(bytes);
      return [{ path: ['资料归档', item.id, `V${item.version}`, ...item.name.split('/')], bytes, checksum },...(item.name.startsWith('成果档案/')?[{path:['成果档案','导入材料',item.id,`V${item.version}`,...item.name.split('/').slice(1)],bytes,checksum}]:[])];
    }))).flat();
    for (const file of files) await writeImmutableFile(binding.handle, file.path, file.bytes, file.sha256);
    for (const file of referenceFiles) await writeImmutableFile(binding.handle, file.path, file.bytes, file.checksum);
    if(binding.managed){
      const programs:{path:string[];sha256:string;bytes:Uint8Array<ArrayBuffer>}[]=[];
      try{
        const root=await binding.handle.getDirectoryHandle('programs');
        for await(const directory of (root as FileSystemDirectoryHandle&{values():AsyncIterableIterator<FileSystemHandle>}).values()){
          if(directory.kind!=='directory')continue;
          if(programs.length>=1000)throw new Error('单独程序超过保存数量限制，请另行备份。');
          const handle=await root.getDirectoryHandle(directory.name);
          for(const name of ['main.py','program.json']){const file=await(await handle.getFileHandle(name)).getFile();if(file.size>65536)throw new Error('单独程序文件过大。');const bytes=new Uint8Array(await file.arrayBuffer());programs.push({path:['programs',directory.name,name],bytes,sha256:await sha256(bytes)});}
        }
      }catch(e){if(!(e instanceof DOMException&&e.name==='NotFoundError'))throw e;}
      const encoded:ManagedFolderFile[]=[...files.map(f=>({path:f.path,sha256:f.sha256,bytes:f.bytes})),...referenceFiles.map(f=>({path:f.path,sha256:f.checksum,bytes:f.bytes})),...programs].map(f=>{
        let binary='';for(let i=0;i<f.bytes.length;i+=8192)binary+=String.fromCharCode(...f.bytes.subarray(i,i+8192));
        return {path:f.path,sha256:f.sha256,content:btoa(binary)};
      });
      const result=await api<ManagedProjectFolder>(`/projects/${binding.projectId}/folder/managed/sync`,'POST',{snapshot:json,expectedCheckpointHash:binding.nativeCheckpointHash??null,files:encoded});
      binding.nativeCheckpointHash=result.checkpointHash;binding.nativePath=result.path;
    }
    if (main !== current.code) {
      await write(binding.handle, primaryFile, current.code);
      binding.mainHash = await hash(current.code);
    }
    await write(binding.handle, PROJECT_FILE, json);
    binding.checkpointHash = await hash(json);
    await rememberFolder(binding);
  };
  // Serializes folder checkpoints across tabs; fingerprints also reject stale writers.
  await lockProjectFolder(snapshot.portableId, task);
}

function database(): Promise<IDBDatabase> {
  return openPlatformDatabase('zhangwen-project-folders', 'folders', 'projectId');
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
    const saved=await new Promise<FolderBinding | null>((resolve, reject) => {
      const request = db.transaction('folders').objectStore('folders').get(projectId);
      request.onsuccess = () => resolve((request.result as FolderBinding | undefined) ?? null);
      request.onerror = () => reject(new Error('无法读取项目文件夹关联，请重新加载项目文件夹。'));
    });
    if(saved&&!saved.managed)return saved;
    const native=await api<ManagedProjectFolder|null>(`/projects/${projectId}/folder/managed`);
    return native?managedBinding(projectId,native,saved??undefined):saved;
  } finally { db.close(); }
}
