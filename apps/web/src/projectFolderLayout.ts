import type { ProjectSnapshot, HardwareResourceBundle } from '../../../packages/contracts/src/platform';

/** Human-readable copies only. Snapshot asset keys remain the portable import contract. */
export interface ProjectFolderFile {
  path: string[];
  sha256: string;
  data: { text: string } | { base64: string };
}

const ASSET_PREFIX = '/api/projects/__PROJECT__/structure/assets/';
function folderName(value: string, fallback: string): string {
  const clean = value.normalize('NFC').replace(/[<>:"/\\|?*\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g, '_')
    .replace(/\s+/g, ' ').replace(/^[. ]+|[. ]+$/g, '');
  return Array.from(clean || fallback).slice(0, 32).join('').replace(/[. ]+$/g, '') || fallback;
}
const versionFolder = (revision: number, name: string, fallback: string) => {
  if (!Number.isSafeInteger(revision) || revision < 1) throw new Error('输出文件版本号无效。');
  return `V${String(revision).padStart(3, '0')}_${folderName(name, fallback)}`;
};
function assetParts(key: string): string[] {
  const parts = key.split('/');
  if (parts.length < 3 || parts.length > 4 || !/^[a-f0-9]{32}$/.test(parts[0]) ||
      !/^ZW-PRODUCT-\d{8}-\d{6}(?:-\d{2})?$/.test(parts[1]) ||
      parts.slice(2).some(p => !/^[a-zA-Z0-9_.-]+$/.test(p) || p === '.' || p === '..')) {
    throw new Error('结构资产路径无效，未覆盖文件夹快照。');
  }
  return parts;
}
function referencedAssets(value: unknown, keys: Set<string>): void {
  if (typeof value === 'string' && value.startsWith(ASSET_PREFIX)) keys.add(value.slice(ASSET_PREFIX.length));
  else if (Array.isArray(value)) value.forEach(item => referencedAssets(item, keys));
  else if (value && typeof value === 'object') Object.values(value).forEach(item => referencedAssets(item, keys));
}

export function projectFolderFiles(snapshot: ProjectSnapshot): ProjectFolderFile[] {
  const files: ProjectFolderFile[] = [];
  const revisions = new Set<number>();
  for (const version of snapshot.versions) {
    if (revisions.has(version.revision)) throw new Error('代码历史版本重复，未写入文件夹。');
    revisions.add(version.revision);
    files.push({ path: ['代码', version.source === 'ai' ? 'AI候选' : '已保存版本',
      versionFolder(version.revision, version.name ?? '', 'MicroPython程序'), 'main.py'],
      sha256: version.checksum, data: { text: version.code } });
  }
  const structure = snapshot.structure;
  if (!structure) return files;
  Object.keys(structure.assets).forEach(assetParts);
  const used = new Set<string>(), structureRevisions = new Set<number>();
  for (const version of structure.versions) {
    if (structureRevisions.has(version.revision)) throw new Error('结构历史版本重复，未写入文件夹。');
    structureRevisions.add(version.revision);
    const keys = new Set<string>();
    referencedAssets(version.result, keys);
    const groups = [...new Set([...keys].map(key => assetParts(key).slice(0, 2).join('/')))].sort();
    const name = versionFolder(version.revision, version.name || version.result.title || version.prompt.slice(0, 32), '结构设计');
    for (const key of [...keys].sort()) {
      const asset = structure.assets[key];
      if (!asset) throw new Error('结构版本缺少导出文件，未覆盖文件夹快照。');
      used.add(key);
      const parts = assetParts(key);
      files.push({ path: ['结构', version.designType === 'laser' ? '激光造物' : '3D造物', name,
        ...(groups.length > 1 ? [`文件组${String(groups.indexOf(parts.slice(0, 2).join('/')) + 1).padStart(2, '0')}`] : []), ...parts.slice(2)],
        sha256: asset.sha256, data: { base64: asset.content } });
    }
  }
  if (Object.keys(structure.assets).some(key => !used.has(key))) throw new Error('结构文件缺少版本关联，未覆盖文件夹快照。');
  return files;
}

export function hardwareFolderFiles(bundle: HardwareResourceBundle): ProjectFolderFile[] {
  if (bundle.schemaVersion !== 1 || !Array.isArray(bundle.modules) || bundle.modules.length > 128) throw new Error('硬件资料格式无效。');
  const files: ProjectFolderFile[] = [], used = new Set<string>();
  let size = 0;
  for (const module of bundle.modules) {
    if (!/^[a-zA-Z0-9_-]{1,120}$/.test(module.id) || !/^[a-f0-9]{64}$/.test(module.revision) ||
        typeof module.name !== 'string' || !Array.isArray(module.files) || module.files.length > 500) throw new Error('模块资料身份无效。');
    for (const file of module.files) {
      if (!Array.isArray(file.path) || !file.path.length || file.path.length > 8 || file.path.some(part =>
        typeof part !== 'string' || !/^[\p{L}\p{N}_. -]{1,100}$/u.test(part) || /^[. ]|[. ]$/.test(part) ||
        /^(con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)/i.test(part)) || !/^[a-f0-9]{64}$/.test(file.sha256) ||
        typeof file.content !== 'string' || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(file.content)) {
        throw new Error('硬件资料路径或摘要无效，未覆盖文件夹快照。');
      }
      size += file.content.length;
      if (size > 17 * 1024 * 1024 || files.length >= 4000) throw new Error('硬件资料超过输出容量。');
      const path = ['硬件', `${folderName(module.name, '模块')}_${module.id}`, `资料版本_${module.revision.slice(0, 16)}`, ...file.path];
      const key = path.join('/').normalize('NFC').toLowerCase();
      if (used.has(key)) throw new Error('硬件资料输出路径重复。');
      used.add(key); files.push({ path, sha256: file.sha256, data: { base64: file.content } });
    }
  }
  return files;
}
