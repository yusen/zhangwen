"""Reviewed supplements live in canonical Hardware Skill examples/usage.md.

These documents describe suggested wiring, never actual connections or test receipts.
Installation uses the original atomic/conflict-checked Hardware Skill writer.
"""
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from zhangwen.hardware.hardware_skills import HardwareSkillValidationError
from .models import Boundary

START = '<!-- zhangwen:module-guides:v1 -->'
END = '<!-- /zhangwen:module-guides:v1 -->'
PATTERN = re.compile(re.escape(START) + r'\s*```json\s*\n(.*?)\n```\s*' + re.escape(END), re.S)
SUPPLEMENTS = Path(__file__).resolve().parents[4] / 'resources/hardware-skills'


class Choice(Boundary):
    value: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=160)


class GuideField(Boundary):
    key: str = Field(pattern=r'^[A-Za-z][A-Za-z0-9_]{0,31}$')
    label: str = Field(min_length=1, max_length=80)
    default: str = Field(min_length=1, max_length=160)
    options: list[Choice] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def choices_valid(self):
        values = [item.value for item in self.options]
        if len(set(values)) != len(values) or self.default not in values:
            raise ValueError('invalid option defaults')
        return self


class Connection(Boundary):
    signal: str = Field(min_length=1, max_length=80)
    target: str = Field(min_length=1, max_length=160)


class ModuleGuide(Boundary):
    boardId: str
    kind: Literal['functional', 'diagnostic', 'reference']
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=700)
    fields: list[GuideField] = Field(max_length=16)
    connections: list[Connection] = Field(max_length=16)
    notes: list[str] = Field(max_length=12)
    sources: list[str] = Field(max_length=8)
    codeTemplate: str = Field(max_length=16000)

    @model_validator(mode='after')
    def template_valid(self):
        keys = [item.key for item in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError('duplicate guide field')
        referenced = set(re.findall(r'\{\{([A-Za-z0-9_]+)\}\}', self.codeTemplate + '\n'.join(item.target for item in self.connections)))
        if not referenced.issubset(keys) or any(not url.startswith('https://') for url in self.sources):
            raise ValueError('invalid guide references')
        if any(len(note) > 700 for note in self.notes) or '\\u0000' in self.model_dump_json():
            raise ValueError('invalid guide text')
        return self


class I2CInfo(Boundary):
    defaultAddress: str | None = None
    addresses: list[str] = Field(max_length=32)
    notes: str = Field(max_length=1200)
    sources: list[str] = Field(max_length=8)

    @model_validator(mode='after')
    def addresses_valid(self):
        if (len(set(self.addresses)) != len(self.addresses)
                or any(not valid_i2c_address(value) for value in self.addresses)
                or (self.defaultAddress is not None and self.defaultAddress not in self.addresses)
                or any(not url.startswith('https://') for url in self.sources)):
            raise ValueError('invalid I2C address reference')
        return self


def valid_i2c_address(value):
    return isinstance(value, str) and re.fullmatch(r'0[xX][0-9a-fA-F]{1,2}', value) is not None and 1 <= int(value, 16) <= 0x7f


class GuideDocument(Boundary):
    format: Literal['zhangwen.module-guides/v1'] = Field(alias='schema')
    componentId: str
    guides: list[ModuleGuide] = Field(min_length=1, max_length=5)
    i2c: I2CInfo | None = None


def parse_document(content, component_id, boards):
    match = PATTERN.search(content)
    if not match:
        if START in content or END in content:
            raise HardwareSkillValidationError('模块示例资料区不完整，原文件已保留。')
        return []
    try:
        if len(PATTERN.findall(content)) != 1:
            raise ValueError('duplicate document')
        doc = GuideDocument.model_validate_json(match[1])
        ids = [item.boardId for item in doc.guides]
        if doc.componentId != component_id or len(ids) != len(set(ids)) or not set(ids).issubset(boards):
            raise ValueError('guide identity mismatch')
        return [item.model_dump() for item in doc.guides]
    except ValueError as exc:
        raise HardwareSkillValidationError('模块案例资料格式无效。') from exc


def guides(detail, boards):
    content = next((item.content for item in detail.files if item.path == 'examples/usage.md'), '')
    return parse_document(content, detail.componentId, boards)


def i2c_info(detail, boards):
    content = next((item.content for item in detail.files if item.path == 'examples/usage.md'), '')
    items = guides(detail, boards)
    match = PATTERN.search(content)
    explicit = GuideDocument.model_validate_json(match[1]).i2c if match else None
    uses_i2c = explicit or re.search(r'I2C|I²C|IIC', detail.specification.electrical.communicationProtocol, re.I) or any(
        field['key'] == 'interface' and any(choice['value'] == 'I2C' for choice in field['options'])
        for item in items for field in item['fields'])
    if not uses_i2c or detail.category.value == 'MCU':
        return None
    if explicit:
        return explicit.model_dump()
    raw = detail.specification.electrical.i2cAddress
    addresses = [f'0x{int(raw, 16):02x}'] if valid_i2c_address(raw) else []
    for item in items:
        for field in item['fields']:
            if field['key'] == 'address':
                addresses.extend(f'0x{int(choice["value"], 16):02x}' for choice in field['options'] if valid_i2c_address(choice['value']))
    addresses = list(dict.fromkeys(addresses))
    return dict(defaultAddress=addresses[0] if addresses else None, addresses=addresses,
                notes='地址来自模块原规格或配套案例，实际以模块版本、跳线及扫描结果为准。' if addresses else '地址待核实：查阅官方资料，或使用当前主控适用的I²C扫描程序确认；不猜测地址。',
                sources=list(dict.fromkeys(url for item in items for url in item['sources']))[:3])


def values(guide, setup=None):
    result = {field['key']: field['default'] for field in guide['fields']}
    for key, value in (setup or {}).items():
        field = next((field for field in guide['fields'] if field['key'] == key), None)
        if field is None or (value not in {choice['value'] for choice in field['options']}
                             and not (key == 'address' and valid_i2c_address(value))):
            raise HardwareSkillValidationError('接线选项已变化，请刷新模块资料后重新选择。')
        result[key] = value
    pins = [value for key, value in result.items() if key in {'sig', 'sig2', 'sig3', 'rx', 'tx'}]
    if len(set(pins)) != len(pins):
        raise HardwareSkillValidationError('多路信号不能使用同一引脚，请分别选择。')
    return result


def render(guide, setup=None):
    selected = values(guide, setup)
    return re.sub(r'\{\{([A-Za-z0-9_]+)\}\}', lambda match: selected[match[1]], guide['codeTemplate'])


def setup_text(guide, setup=None):
    selected = values(guide, setup)
    return '；'.join(field['label'] + '：' + next((choice['label'] for choice in field['options']
        if choice['value'] == selected[field['key']]), selected[field['key']]) for field in guide['fields'])


def install(repository, boards):
    if not SUPPLEMENTS.is_dir():
        raise RuntimeError('模块案例补充资料缺失，请重新下载完整项目。')
    changed = 0
    for source in sorted(SUPPLEMENTS.glob('*/examples/reviewed.md')):
        if source.is_symlink() or any(parent.is_symlink() for parent in source.parents if parent != SUPPLEMENTS.parent):
            raise HardwareSkillValidationError('模块补充资料不能使用符号链接。')
        skill_name = source.parent.parent.name
        detail = repository.get_skill(skill_name, include_archived=True)
        if detail.status.value != 'ACTIVE':
            continue
        incoming = source.read_text(encoding='utf-8')
        parsed = parse_document(incoming, detail.componentId, boards)
        if not parsed:
            raise HardwareSkillValidationError('模块补充资料为空。')
        original = next(item.content for item in detail.files if item.path == 'examples/usage.md')
        # Parse existing before replacing; never silently repair malformed user data.
        parse_document(original, detail.componentId, boards)
        section = PATTERN.search(incoming)[0]
        current = PATTERN.search(original)
        if current and current[0] == section:
            continue
        merged = PATTERN.sub(lambda _: section, original) if current else original.rstrip() + '\n\n' + section + '\n'
        repository.update_file(skill_name, path='examples/usage.md', content=merged, expected_revision=detail.revision)
        changed += 1
    return changed
