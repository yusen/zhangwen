import type { ProjectProgramRecord, ProgramRunSubmission, UploadReceipt } from '../../../packages/contracts/src/mu';
import { ensureFolderPermission, PROJECT_FILE, type FolderBinding, type ProjectDirectory } from './projectFolders';
import { sha256 } from './serial';

export const PROGRAMS_DIRECTORY = 'programs';
export interface ProjectProgram { directory: string; record: ProjectProgramRecord }
const digest = (value: string) => sha256(new TextEncoder().encode(value));
const safeSegment = (value: string) => !!value && !/[\\/\x00-\x1f]/.test(value) && !['.', '..'].includes(value);
const validDate = (value: unknown): value is string => typeof value === 'string' && value.length <= 40 && Number.isFinite(Date.parse(value));
const nullableDate = (value: unknown) => value === null || validDate(value);
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
async function read(directory: FileSystemDirectoryHandle, filename: string, limit: number) {
  const file = await (await directory.getFileHandle(filename)).getFile();
  if (file.size > limit) throw new Error(`${filename} 超出大小限制，未载入。`);
  return new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
}
async function write(directory: FileSystemDirectoryHandle, filename: string, data: string) {
  const stream = await (await directory.getFileHandle(filename, { create: true })).createWritable();
  try { await stream.write(data); await stream.close(); } catch (error) { await stream.abort().catch(() => {}); throw error; }
}
function parseRecord(raw: string): ProjectProgramRecord {
  const value: unknown = JSON.parse(raw);
  if (!object(value) || value.format !== 'zhangwen-program' || value.schemaVersion !== 1 ||
    typeof value.name !== 'string' || !value.name.trim() || value.name.length > 80 || !validDate(value.createdAt) ||
    typeof value.boardId !== 'string' || !value.boardId || value.boardId.length > 150 ||
    typeof value.boardName !== 'string' || !value.boardName || value.boardName.length > 250 ||
    !Array.isArray(value.componentIds) || value.componentIds.length > 32 || value.componentIds.some(id => typeof id !== 'string' || id.length > 150) ||
    typeof value.checksum !== 'string' || !/^[a-f0-9]{64}$/.test(value.checksum) ||
    !(value.sourceRevision === null || (Number.isSafeInteger(value.sourceRevision) && Number(value.sourceRevision) > 0)) ||
    !object(value.verification) || typeof value.verification.observed !== 'string' || !['unconfirmed', 'passed', 'failed'].includes(value.verification.observed) ||
    typeof value.verification.note !== 'string' || value.verification.note.length > 2000 ||
    !nullableDate(value.verification.uploadVerifiedAt) || !nullableDate(value.verification.runSubmittedAt)) throw new Error('程序资料格式无效，未载入。');
  return value as unknown as ProjectProgramRecord;
}
async function programDirectory(binding: FolderBinding, directory: string) {
  if (!safeSegment(directory)) throw new Error('程序文件夹名称无效。');
  return (await binding.handle.getDirectoryHandle(PROGRAMS_DIRECTORY)).getDirectoryHandle(directory);
}
export async function listProjectPrograms(binding: FolderBinding): Promise<{ programs: ProjectProgram[]; issues: string[] }> {
  await ensureFolderPermission(binding);
  let root: FileSystemDirectoryHandle;
  try { root = await binding.handle.getDirectoryHandle(PROGRAMS_DIRECTORY); }
  catch (error) { if (error instanceof DOMException && error.name === 'NotFoundError') return { programs: [], issues: [] }; throw error; }
  const programs: ProjectProgram[] = [], issues: string[] = [];
  let count = 0;
  for await (const handle of (root as FileSystemDirectoryHandle & { values(): AsyncIterableIterator<FileSystemHandle> }).values()) {
    if (++count > 1000) { issues.push('程序文件夹超过1000项，仅显示前1000项。'); break; }
    if (handle.kind !== 'directory') continue;
    try { programs.push({ directory: handle.name, record: parseRecord(await read(await root.getDirectoryHandle(handle.name), 'program.json', 32_768)) }); }
    catch { issues.push(`${handle.name}：资料不完整或格式无效，原文件保留。`); }
  }
  programs.sort((a, b) => b.record.createdAt.localeCompare(a.record.createdAt));
  return { programs, issues };
}
export async function readProjectProgram(binding: FolderBinding, directory: string): Promise<ProjectProgram & { code: string }> {
  await ensureFolderPermission(binding);
  const handle = await programDirectory(binding, directory);
  const record = parseRecord(await read(handle, 'program.json', 32_768));
  const code = await read(handle, 'main.py', 65_536);
  if (code.includes('\0') || await digest(code) !== record.checksum) throw new Error('程序代码与记录的摘要不一致，未载入。原文件保留。');
  return { directory, record, code };
}
/** Save-as carries verified archives into the new project folder without replacing existing files. */
export async function copyProjectPrograms(source: FolderBinding, destination: ProjectDirectory): Promise<void> {
  if (await source.handle.isSameEntry(destination)) return;
  const { programs, issues } = await listProjectPrograms(source);
  if (issues.length) throw new Error('原项目存在不完整的程序资料，请核对后重试另存文件夹。原文件保留。');
  if (!programs.length) return;
  const root = await destination.getDirectoryHandle(PROGRAMS_DIRECTORY, { create: true });
  for (const program of programs) {
    const verified = await readProjectProgram(source, program.directory);
    let existing: FileSystemDirectoryHandle | null = null;
    try { existing = await root.getDirectoryHandle(program.directory); }
    catch (error) { if (!(error instanceof DOMException && error.name === 'NotFoundError')) throw error; }
    if (existing) {
      const record = parseRecord(await read(existing, 'program.json', 32_768));
      if (JSON.stringify(record) !== JSON.stringify(verified.record) || await read(existing, 'main.py', 65_536) !== verified.code) throw new Error('目标文件夹存在不同的同名程序，未覆盖。请选择其他文件夹。');
      continue;
    }
    const handle = await root.getDirectoryHandle(program.directory, { create: true });
    await write(handle, 'main.py', verified.code);
    if (await digest(await read(handle, 'main.py', 65_536)) !== verified.record.checksum) throw new Error('另存程序回读不一致，原项目保留。');
    await write(handle, 'program.json', JSON.stringify(verified.record, null, 2) + '\n');
    if (JSON.stringify(parseRecord(await read(handle, 'program.json', 32_768))) !== JSON.stringify(verified.record)) throw new Error('另存程序资料回读不一致，原项目保留。');
  }
}
export async function saveProjectProgram(binding: FolderBinding, input: {
  name: string; code: string; boardId: string; boardName: string; componentIds: string[]; sourceRevision: number | null;
  observed: ProjectProgramRecord['verification']['observed']; note: string;
  receipt: UploadReceipt | null; run: ProgramRunSubmission | null;
}): Promise<ProjectProgram> {
  await ensureFolderPermission(binding, true);
  const code = input.code, checksum = await digest(code);
  if (!code.trim() || new TextEncoder().encode(code).length > 65_536 || code.includes('\0')) throw new Error('程序须为非空 UTF-8 文本，且不超过64 KiB。');
  if (!binding.checkpointHash || await digest(await read(binding.handle, PROJECT_FILE, 32 * 1024 * 1024)) !== binding.checkpointHash) throw new Error('项目文件夹尚未完成同步，或已被外部修改。请保存或重新加载后再保存程序。');
  const receipt = input.receipt?.projectId === binding.projectId && input.receipt.sha256 === checksum && input.receipt.revision === input.sourceRevision ? input.receipt : null;
  const run = receipt && input.run?.projectId === binding.projectId && input.run.sha256 === checksum && input.run.boardId === input.boardId && input.run.revision === receipt.revision && input.run.submittedAt >= receipt.verifiedAt ? input.run : null;
  const createdAt = new Date().toISOString();
  const record = parseRecord(JSON.stringify({ format: 'zhangwen-program', schemaVersion: 1, name: input.name.trim(), createdAt,
    boardId: input.boardId, boardName: input.boardName, componentIds: [...input.componentIds], checksum, sourceRevision: input.sourceRevision,
    verification: { observed: input.observed, note: input.note.trim(), uploadVerifiedAt: receipt?.verifiedAt ?? null, runSubmittedAt: run?.submittedAt ?? null } }));
  const shortName = record.name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/[. ]+$/g, '').slice(0, 32) || 'program';
  const directory = `${createdAt.replace(/[-:]/g, '').slice(0, 15)}-${shortName}-${crypto.randomUUID()}`;
  const root = await binding.handle.getDirectoryHandle(PROGRAMS_DIRECTORY, { create: true });
  const handle = await root.getDirectoryHandle(directory, { create: true });
  // Each save has a unique folder. The metadata is the completion marker, written after code readback.
  await write(handle, 'main.py', code);
  if (await digest(await read(handle, 'main.py', 65_536)) !== checksum) throw new Error('程序写入回读不一致，未标记保存完成。');
  await write(handle, 'program.json', JSON.stringify(record, null, 2) + '\n');
  await readProjectProgram(binding, directory);
  return { directory, record };
}
