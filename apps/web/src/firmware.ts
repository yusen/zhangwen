import { sha256 } from './serial';
import type { FirmwareProfile } from '../../../packages/contracts/src/platform';

export interface FlashPeer {
  chip: { CHIP_NAME: string };
  writeFlash(options: { fileArray: { data: string; address: number }[]; flashSize: string; flashMode: string; flashFreq: string; eraseAll: boolean; compress: boolean; reportProgress?: (index: number, written: number, total: number) => void }): Promise<void>;
}
export async function loadDefaultFirmware(profile: FirmwareProfile, signal?: AbortSignal): Promise<Uint8Array> {
  const image = profile.image;
  if (!image || image.url !== `/api/firmware/${profile.boardId}/image`) throw new Error('默认固件地址无效。');
  const response = await fetch(image.url, {signal, cache: 'no-store'});
  if (!response.ok) throw new Error('本地默认固件无法读取，请检查部署文件。');
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.length !== image.size || await sha256(bytes) !== image.sha256) throw new Error('默认固件大小或SHA-256不符，已阻止刷入。');
  checkImage(bytes, profile, profile.offset);
  return bytes;
}
export function checkImage(bytes: Uint8Array, profile: FirmwareProfile, address: number): void {
  if (bytes.length < 24 || bytes.length > 16 * 1024 * 1024 || !Number.isInteger(address) || address < 0 || address % 4096 || address + bytes.length > 16 * 1024 * 1024) throw new Error('固件须为24字节至16MiB的 .bin，偏移须为4KiB对齐的有效地址。');
  const header = bytes[0] === 0xe9 ? 0 : address === 0 && bytes[0x1000] === 0xe9 ? 0x1000 : -1;
  if (header < 0 || header + 24 > bytes.length) throw new Error('未找到完整 ESP 启动镜像头。请选择厂商提供的完整固件 .bin，确认烧录偏移。');
  const chip = bytes[header + 12] | bytes[header + 13] << 8;
  const expected = { ESP32: 0, 'ESP32-S3': 9, 'ESP32-C3': 5 }[profile.chip];
  if (chip !== expected) throw new Error(`固件芯片 ID ${chip} 与 ${profile.chip} 不一致。`);
  if ((profile.chip === 'ESP32' && address + header !== 0x1000) || (profile.chip !== 'ESP32' && address + header !== 0)) throw new Error('镜像启动地址不匹配。此入口只支持包含 bootloader 的完整固件，请按官方说明核对偏移。');
}
function binary(bytes: Uint8Array): string {
  const chunks: string[] = [];
  for (let offset = 0; offset < bytes.length; offset += 8192) chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 8192)));
  return chunks.join('');
}
export async function flashFirmware(peer: FlashPeer, profile: FirmwareProfile, bytes: Uint8Array, address: number, capacity: number, progress: (phase: string, value: number) => void): Promise<void> {
  checkImage(bytes, profile, address);
  if (peer.chip.CHIP_NAME !== profile.chip) throw new Error(`设备芯片 ${peer.chip.CHIP_NAME} 与当前主控 ${profile.chip} 不一致。`);
  const size = Math.ceil(bytes.length / 4096) * 4096;
  if (!Number.isSafeInteger(capacity) || capacity <= 0 || address + size > capacity) throw new Error('固件超出设备 Flash 容量或容量无法确认。');
  await peer.writeFlash({ fileArray: [{ data: binary(bytes), address }], flashSize: 'keep', flashMode: 'keep', flashFreq: 'keep', eraseAll: false, compress: true, reportProgress: (_i, done, total) => progress('写入', done / total) });
}
