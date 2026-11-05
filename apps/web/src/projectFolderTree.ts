export interface FolderContents { entries: FileSystemHandle[]; truncated: boolean }
/** Lazy directory enumeration; never reads or executes file contents. */
export async function folderContents(directory: FileSystemDirectoryHandle): Promise<FolderContents> {
  const entries: FileSystemHandle[] = [];
  let truncated = false;
  for await (const handle of (directory as FileSystemDirectoryHandle & { values(): AsyncIterableIterator<FileSystemHandle> }).values()) {
    if (entries.length === 500) { truncated = true; break; }
    entries.push(handle);
  }
  entries.sort((a, b) => a.kind === b.kind ? a.name.localeCompare(b.name, 'zh-CN', { numeric: true }) : a.kind === 'directory' ? -1 : 1);
  return { entries, truncated };
}
export const folderPurposes: Record<string, string> = {
  'zhangwen.project.json': '项目入口，包含配置、历史对话与版本；加载项目时读取',
  'main.py': '当前已保存的 MicroPython 程序',
  'chat-task.txt': '当前已保存的原生 Claw 任务',
  '代码': '已保存代码、AI 生成稿和其他编程历史版本',
  'programs': '单独保存的测试程序、接线与测试备注',
  '结构': '3D造物与激光造物的各版模型、图纸和建模文件',
  '硬件': '主控与模块的资料、示例、图片和结构档案',
  '学习与验收': '作品目标、测试观察、成果报告和图片附件',
  '参考资料': '可通过项目资料导入的原始文件',
  '资料归档': '已导入项目的参考资料与版本',
};

export interface FolderSearchResult {
  files: { handle: FileSystemFileHandle; path: string }[];
  truncated: boolean;
  unreadable: number;
}
/** Bounded, cancellable name search. Never opens file contents. */
export async function searchFolderFiles(root: FileSystemDirectoryHandle, query: string, signal: AbortSignal): Promise<FolderSearchResult> {
  const result: FolderSearchResult = { files: [], truncated: false, unreadable: 0 };
  const pending = [{ handle: root, path: '', depth: 0 }];
  const needle = query.trim().toLocaleLowerCase();
  let scanned = 0;
  while (pending.length) {
    signal.throwIfAborted();
    if (scanned >= 2000 || result.files.length >= 200) { result.truncated = true; break; }
    const current = pending.shift()!;
    let contents: FolderContents;
    try { contents = await folderContents(current.handle); }
    catch (error) { signal.throwIfAborted(); if (!current.depth) throw error; result.unreadable++; continue; }
    signal.throwIfAborted();
    result.truncated ||= contents.truncated;
    for (const entry of contents.entries) {
      signal.throwIfAborted();
      if (scanned >= 2000 || result.files.length >= 200) { result.truncated = true; break; }
      scanned++;
      const path = current.path + entry.name;
      if (entry.kind === 'directory') {
        if (current.depth < 9) pending.push({ handle: entry as FileSystemDirectoryHandle, path: path + '/', depth: current.depth + 1 });
        else result.truncated = true;
      } else if (path.toLocaleLowerCase().includes(needle)) result.files.push({ handle: entry as FileSystemFileHandle, path });
    }
  }
  return result;
}

export type ProjectFilePreview = { file: File; kind: 'text'; text: string } | { file: File; kind: 'image' | 'unsupported'; note?: string };
/** Explicit selection only. HTML/SVG are displayed as text, never executed. */
export async function projectFilePreview(handle: FileSystemFileHandle): Promise<ProjectFilePreview> {
  const file = await handle.getFile();
  if (/\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(file.name)) {
    return file.size <= 8 * 1024 * 1024 ? { file, kind: 'image' } : { file, kind: 'unsupported', note: '图片超过8MiB，请在系统文件夹中查看。' };
  }
  if (!/\.(txt|md|markdown|py|lua|json|csv|ya?ml|xml|svg|html?|css|[cm]?js|[cm]?ts|tsx|jsx|toml|ini|cfg|log|c|cpp|h|hpp|ino|scad|dxf)$/i.test(file.name)) {
    return { file, kind: 'unsupported', note: '此格式请在系统文件夹中使用对应软件打开。' };
  }
  if (file.size > 512 * 1024) return { file, kind: 'unsupported', note: '文本超过512KiB，请在系统文件夹中查看。' };
  try {
    const text = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
    if (text.includes('\0')) throw new Error('binary');
    return { file, kind: 'text', text };
  } catch { return { file, kind: 'unsupported', note: '此文件不是可预览的UTF-8文本，请在系统文件夹中查看。' }; }
}
