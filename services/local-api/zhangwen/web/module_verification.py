"""User-reported module/controller checks in the canonical usage document."""
import json
import re

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
