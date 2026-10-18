"""Readable labels derived without rewriting immutable historic artifacts."""
import json
import re


def short_name(value: str, fallback: str = '程序更新') -> str:
    value = re.sub(r'\s+', ' ', value).strip(' #\t\r\n')
    value = re.sub(r'[`<>\x00-\x1f]', '', value)
    return value[:36] or fallback


def code_name(code: str, reply: str | None = None) -> str:
    if reply:
        try:
            summary = json.loads(reply).get('summary', '')
            if isinstance(summary, str) and summary.strip():
                return short_name(summary)
        except (ValueError, AttributeError):
            pass
    for line in code.splitlines()[:20]:
        if line.strip().startswith('#') and not re.search(r'coding[:=]|^#!|^#\s*(掌问|MicroPython)\s*[·：:]?\s*$', line, re.I):
            name = line.strip().lstrip('#').strip()
            if len(name) > 2:
                return short_name(name)
    match = re.search(r'print\(\s*[\"\']([^\"\'\n]{3,60})', code)
    return short_name(match[1]) if match else 'MicroPython 程序'
