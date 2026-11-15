"""Programming capabilities belong to the installed Hardware Skill."""
import json
import re


def mode_for_detail(detail):
    source = next((f.content for f in detail.files if f.path == 'references/sources.md'), '')
    match = re.search(r'```zhangwen:programming:v1\s*\n(.*?)\n```', source, re.S)
    if not match:
        return 'micropython'
    data = json.loads(match[1])
    if data != {'schema': 'zhangwen.programming/v1', 'mode': 'chat-coding', 'transport': 'claw-webim'}:
        raise ValueError('主控编程方式描述无效。')
    return data['mode']


def board_mode(repo, board_id):
    return mode_for_detail(repo.skills.get_active_by_component_id(board_id)) if board_id else 'micropython'


def task_file(repo, board_id):
    return 'chat-task.txt' if board_mode(repo, board_id) == 'chat-coding' else 'main.py'
