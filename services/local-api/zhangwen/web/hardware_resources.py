"""Resource paths only; electrical/mechanical facts retain their existing schemas."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path, PurePosixPath

from zhangwen.hardware.hardware_skills import (
    HardwareSkillValidationError, MAX_SKILL_FILE_BYTES, MAX_SKILL_PACKAGE_BYTES, _normalize_text,
)

ROOT = Path(__file__).resolve().parents[4] / 'resources'
CATALOG = ROOT / 'hardware-skills'


@lru_cache(maxsize=1)
def index():
    value = json.loads((ROOT/'hardware-resources.json').read_text(encoding='utf-8'))
    if value.get('schema') != 'zhangwen.hardware-resources/v1':
        raise HardwareSkillValidationError('硬件资源索引版本无效。')
    return value


def resource_path(relative):
    path = PurePosixPath(relative)
    if path.is_absolute() or any(p in {'..', '.'} for p in path.parts) or '\\' in relative or ':' in relative:
        raise HardwareSkillValidationError('硬件资源路径无效。')
    target = ROOT.joinpath(*path.parts)
    if not target.resolve().is_relative_to(ROOT.resolve()) or any(p.is_symlink() for p in [target, *target.parents] if p != ROOT.parent):
        raise HardwareSkillValidationError('硬件资源不能越出目录或使用符号链接。')
    return target


def source_files(root, manifest):
    """Validate the aggregate source tree, then use the original Skill validator.

    Extra references are read only from release resources. User Skill packages
    still go through the unchanged, fixed legacy file whitelist.
    """
    record = index()['modules'].get(root.name)
    if not record or record['componentId'] != manifest.componentId:
        raise HardwareSkillValidationError('模块资源与Hardware Skill身份不一致。')
    core = {'manifest.json', *manifest.files, *(item.path for item in manifest.media)}
    extra = record['files']
    for relative in extra:
        if not relative.startswith(('structure/', 'programming/')) and relative != 'examples/reviewed.md':
            raise HardwareSkillValidationError('模块补充资源路径不在允许范围。')
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise HardwareSkillValidationError('模块资源不允许符号链接。')
        if path.is_file(): actual.add(path.relative_to(root).as_posix())
    if actual != core | set(extra) or core & set(extra):
        raise HardwareSkillValidationError('模块资源文件树与索引不一致。')
    for relative, digest in extra.items():
        path = resource_path(f'hardware-skills/{root.name}/{relative}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise HardwareSkillValidationError('模块补充资源摘要不一致。')
    result, total = {}, 0
    for relative in manifest.files:
        raw = (root/relative).read_bytes(); total += len(raw)
        if len(raw) > MAX_SKILL_FILE_BYTES or total > MAX_SKILL_PACKAGE_BYTES:
            raise HardwareSkillValidationError('Hardware Skill内容超出大小限制。')
        result[relative] = _normalize_text(raw.decode('utf-8'))
    return result


def structure_profiles():
    profiles, seen = [], set()
    for entry in index()['structure']['profiles']:
        raw = resource_bytes(entry['path'])
        profile = json.loads(raw.decode('utf-8'))
        if profile['id'] != entry['id'] or profile['id'] in seen:
            raise HardwareSkillValidationError('结构资源身份重复或不一致。')
        seen.add(profile['id'])
        if entry['skillName']:
            owner = index()['modules'].get(entry['skillName'])
            if not owner or owner['componentId'] != entry['componentId']:
                raise HardwareSkillValidationError('结构资源未绑定到原模块。')
        elif entry['componentId'] is not None:
            raise HardwareSkillValidationError('结构专用件不能声明未登记的电子模块。')
        profiles.append({**profile, 'componentId':entry['componentId'], 'skillName':entry['skillName']})
    return profiles


def resource_bytes(relative):
    raw = resource_path(relative).read_bytes()
    digest = index().get('structureFiles', {}).get(relative)
    if digest is None or hashlib.sha256(raw).hexdigest() != digest:
        raise HardwareSkillValidationError('结构资源摘要不一致。')
    return raw


def programming_root(skill_name):
    if skill_name not in index()['modules']:
        raise HardwareSkillValidationError('主控编程资料不存在。')
    return resource_path(f'hardware-skills/{skill_name}/programming')
