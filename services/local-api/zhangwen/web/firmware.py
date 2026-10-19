"""Pinned official images, checked locally; flashing remains browser-only."""
import hashlib
import json
from pathlib import Path
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[4] / 'resources' / 'firmware'
PROFILES = {
    "hw_labplus_mpython_v2": ("ESP32", 0x1000, "https://mpython.readthedocs.io/zh-cn/master/"),
    "hw_labplus_mpython_esp32s3_v3": ("ESP32-S3", 0, "https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/"),
    "hw_seed_unihiker_k10": ("ESP32-S3", 0, "https://www.unihiker.com/wiki/K10/GettingStarted/gettingstarted_mpy/"),
    "hw_seeed_xiao_esp32s3_sense": ("ESP32-S3", 0, "https://wiki.seeedstudio.com/xiao_esp32s3_micropython/"),
    "hw_esp32_generic_c3": ("ESP32-C3", 0, "https://micropython.org/download/ESP32_GENERIC_C3/"),
}


def firmware_profile(board_id):
    chip, offset, documentation = PROFILES[board_id]
    manifest = json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))
    result = {"boardId": board_id, "chip": chip, "offset": offset, "documentation": documentation}
    image = manifest['images'].get(board_id)
    if image:
        result['offset'] = image['offset']
        result['image'] = {k: image[k] for k in ('name', 'version', 'sha256', 'size', 'sourceUrl', 'notes')}
        result['image']['url'] = f'/api/firmware/{board_id}/image'
    else:
        result['unavailable'] = manifest['unavailable'].get(board_id, '暂无已核实的默认固件。')
    return result


def firmware_image(board_id):
    profile = firmware_profile(board_id)
    image = profile.get('image')
    if not image:
        raise HTTPException(404, profile['unavailable'])
    path = ROOT / image['name']
    if not path.is_file() or path.is_symlink() or path.stat().st_size != image['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != image['sha256']:
        raise HTTPException(503, '本地固件缺失或摘要不符，请修复部署文件；未访问设备。')
    return path
