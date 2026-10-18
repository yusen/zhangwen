"""User-declared board scope in the canonical Hardware Skill usage document.

Independent of generated guides and per-board examples; never verification.
"""
import json
import re

from zhangwen.hardware.hardware_skills import HardwareSkillValidationError

START = '<!-- zhangwen:module-support:v1 -->'
END = '<!-- /zhangwen:module-support:v1 -->'
PATTERN = re.compile(re.escape(START) + r'\s*```json\s*\n(.*?)\n```\s*' + re.escape(END), re.S)


def board_ids(value, controllers) -> list[str]:
    if (not isinstance(value, list) or len(value) > len(controllers)
            or any(not isinstance(item, str) or item not in controllers for item in value)
            or len(set(value)) != len(value)):
        raise HardwareSkillValidationError('支持的主控选项无效或重复。')
    return sorted(value)


def parse(content: str, component_id: str, controllers) -> list[str] | None:
    if START not in content and END not in content:
        return None
    matches = list(PATTERN.finditer(content))
    if len(matches) != 1 or content.count(START) != 1 or content.count(END) != 1:
        raise HardwareSkillValidationError('支持主控记录不完整或重复，原资料保留，请先核对。')
    try:
        data = json.loads(matches[0][1])
        if (not isinstance(data, dict) or set(data) != {'schema', 'componentId', 'supportedBoardIds'}
                or data['schema'] != 'zhangwen.module-support/v1' or data['componentId'] != component_id):
            raise ValueError('invalid support document')
        return board_ids(data['supportedBoardIds'], controllers)
    except (ValueError, TypeError) as exc:
        raise HardwareSkillValidationError('支持主控记录格式无效，请核对硬件资料包。') from exc


def replace(content: str, component_id: str, selected: list[str], controllers) -> str:
    parse(content, component_id, controllers)
    data = dict(schema='zhangwen.module-support/v1', componentId=component_id,
                supportedBoardIds=board_ids(selected, controllers))
    return (PATTERN.sub('', content).rstrip() + '\n\n' + START + '\n```json\n'
            + json.dumps(data, ensure_ascii=False, indent=2) + '\n```\n' + END + '\n')
