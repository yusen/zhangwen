"""Release labels are fixed source metadata, never inferred from startup time."""
import json
import re
from datetime import date
from pathlib import Path


def version_key(value: str) -> tuple[int, int, int, int]:
    match = re.fullmatch(r"V0\.4\.(\d{4})\.(\d{2})(\d{2})\.(\d{2,})", value)
    if not match:
        raise ValueError('invalid release version')
    year, month, day, count = map(int, match.groups())
    date(year, month, day)
    if count < 1 or match[4] != f'{count:02d}':
        raise ValueError('invalid daily release count')
    return year, month, day, count


def parse_release_document(content: bytes) -> dict:
    if len(content) > 4096:
        raise ValueError('oversized version document')
    document = json.loads(content)
    value = document.get('version') if isinstance(document, dict) else None
    if not isinstance(value, str):
        raise ValueError('missing release version')
    version_key(value)
    notes = document.get('releaseNotes', [])
    if (not isinstance(notes, list) or len(notes) > 12
            or any(not isinstance(item, str) or not item.strip() or len(item) > 200 for item in notes)):
        raise ValueError('invalid release notes')
    return {'version': value, 'releaseNotes': [item.strip() for item in notes]}


def parse_version_document(content: bytes) -> str:
    return parse_release_document(content)['version']


def read_release(root: Path) -> dict | None:
    path = root / 'version.json'
    if not path.exists():
        return None  # Earlier releases have no version metadata.
    with path.open('rb') as stream:
        return parse_release_document(stream.read(4097))


def read_version(root: Path) -> str | None:
    release = read_release(root)
    return release['version'] if release else None


def next_version(current: str | None, day: date) -> str:
    count = 1
    if current:
        year, month, old_day, previous_count = version_key(current)
        previous_date = date(year, month, old_day)
        if day < previous_date:
            raise ValueError('release date cannot move backwards')
        if day == previous_date:
            count = previous_count + 1
    return f'V0.4.{day:%Y.%m%d}.{count:02d}'
