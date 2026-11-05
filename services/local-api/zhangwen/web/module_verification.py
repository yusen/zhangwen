"""User-reported module/controller checks in the canonical usage document."""
import json
import re
import hashlib
from datetime import UTC, datetime

from zhangwen.hardware.hardware_skills import HardwareSkillValidationError

START = '<!-- zhangwen:module-verification:v1 -->'
END = '<!-- /zhangwen:module-verification:v1 -->'
PATTERN = re.compile(re.escape(START) + r'\s*```json\s*\n(.*?)\n```\s*' + re.escape(END), re.S)


def board_ids(value, controllers):
    if (not isinstance(value, list) or len(value) > len(controllers)
            or any(not isinstance(item, str) or item not in controllers for item in value)
            or len(value) != len(set(value))):
        raise HardwareSkillValidationError('已核实主控选项无效或重复。')
    return sorted(value)


def parse(content, component_id, controllers):
    if START not in content and END not in content:
        return []
    matches = list(PATTERN.finditer(content))
    if len(matches) != 1 or content.count(START) != 1 or content.count(END) != 1:
        raise HardwareSkillValidationError('主控核实记录不完整或重复，原资料已保留，请核对。')
    try:
        data = json.loads(matches[0][1])
        if (not isinstance(data, dict) or set(data) != {'schema', 'componentId', 'verifiedBoardIds'}
                or data['schema'] != 'zhangwen.module-verification/v1' or data['componentId'] != component_id):
            raise ValueError('invalid verification document')
        return board_ids(data['verifiedBoardIds'], controllers)
    except (ValueError, TypeError) as exc:
        raise HardwareSkillValidationError('主控核实记录格式无效，原资料已保留，请核对。') from exc


def replace(content, component_id, selected, controllers):
    parse(content, component_id, controllers)
    data = dict(schema='zhangwen.module-verification/v1', componentId=component_id,
                verifiedBoardIds=board_ids(selected, controllers))
    return (PATTERN.sub('', content).rstrip() + '\n\n' + START + '\n```json\n'
            + json.dumps(data, ensure_ascii=False, indent=2) + '\n```\n' + END + '\n')


RECORD_START = '<!-- zhangwen:verification-records:v2 -->'
RECORD_END = '<!-- /zhangwen:verification-records:v2 -->'
RECORD_PATTERN = re.compile(re.escape(RECORD_START) + r'\s*```json\s*\n(.*?)\n```\s*' + re.escape(RECORD_END), re.S)


def fingerprint(repo, detail, board_id, dimension):
    example = next((e for e in repo.local_examples(detail) if e['boardId'] == board_id), {})
    electrical = detail.specification.electrical.model_dump(exclude={'peakCurrent'})
    code = example.get('code', '')
    if dimension == 'identity':
        value = [detail.componentId, detail.displayName]
    elif dimension == 'electrical':
        value = {k: v for k, v in electrical.items() if k in {'voltage', 'voltageMin', 'voltageMax', 'logicLevel', 'supplyVoltages'}}
    elif dimension == 'wiring':
        value = [example.get('setup'), example.get('i2cAddress'), example.get('notes'), electrical['communicationProtocol'],
                 next((f.content for f in detail.files if f.path == 'references/integration.md'), '')]
    elif dimension == 'mechanical':
        value = {k: v for k, v in (detail.mechanicalProfile or {}).items() if k not in {'revision', 'source'}}
    else:
        value = [code, example.get('setup'), example.get('i2cAddress'), example.get('notes'),
                 electrical.get('communicationProtocol'), electrical.get('driverName'), electrical.get('firmwareRequirement')]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def records(repo, detail, *, latest=True):
    content = next((f.content for f in detail.files if f.path == 'examples/usage.md'), '')
    matches = list(RECORD_PATTERN.finditer(content))
    if not matches and RECORD_START not in content and RECORD_END not in content:
        return []
    try:
        if len(matches) != 1 or content.count(RECORD_START) != 1 or content.count(RECORD_END) != 1:
            raise ValueError()
        items = json.loads(matches[0][1])
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError()
        from .models import VerificationRecordInput
        for item in items:
            VerificationRecordInput.model_validate({k: v for k, v in item.items() if k not in {'codeHash', 'updatedAt', 'fingerprint', 'stale'}})
            if item['boardId'] not in repo.web_controllers or not re.fullmatch('[a-f0-9]{64}', item['fingerprint']):
                raise ValueError()
        if latest:
            newest = {(r['boardId'], r['dimension']): r for r in items}
            items = list(newest.values())
        return [{**r, 'stale': r['fingerprint'] != fingerprint(repo, detail, r['boardId'], r['dimension'])} for r in items]
    except (ValueError, TypeError, KeyError) as exc:
        raise HardwareSkillValidationError('核实记录损坏，原记录未覆盖。') from exc


def save_record(repo, detail, request):
    item = request.record
    if item.boardId not in repo.web_controllers:
        raise HardwareSkillValidationError('请选择有效主控。')
    if item.state in {'documented', 'passed', 'failed'} and not item.evidence.strip():
        raise HardwareSkillValidationError('请填写资料来源或实际测试现象。')
    example = next((e for e in repo.local_examples(detail) if e['boardId'] == item.boardId), {})
    if item.state in {'passed', 'failed'} and item.dimension in {'driver', 'function'}:
        if not example.get('code', '').strip() or not item.wiring.strip() or not item.firmware.strip():
            raise HardwareSkillValidationError('请先保存当前主控案例，再填写固件/库与接线条件；未知版本可明确填写未知。')
    history = [{k: v for k, v in r.items() if k != 'stale'} for r in records(repo, detail, latest=False)]
    if len(history) >= 100:
        raise HardwareSkillValidationError('核实历史已达100条，请导出保留后另建模块版本。')
    record = {**item.model_dump(), 'codeHash': hashlib.sha256(example.get('code', '').encode()).hexdigest(),
              'updatedAt': datetime.now(UTC).isoformat(), 'fingerprint': fingerprint(repo, detail, item.boardId, item.dimension)}
    history.append(record)
    content = next(f.content for f in detail.files if f.path == 'examples/usage.md')
    updated = RECORD_PATTERN.sub('', content).rstrip() + '\n\n' + RECORD_START + '\n```json\n' + json.dumps(history, ensure_ascii=False, indent=2) + '\n```\n' + RECORD_END + '\n'
    return repo.update_file(detail.skillName, path='examples/usage.md', content=updated, expected_revision=request.expectedRevision)
