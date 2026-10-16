"""Create a small macOS launcher for the local Web service; no native app runtime."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIND = 'zhangwen-local-web-launcher'
LAUNCHER = '''#!/bin/bash
set -euo pipefail
resources=$(cd "$(dirname "$0")/../Resources" && pwd)
install_root=$(cat "$resources/install-root.txt")
# A stable command reads current.txt, so updates do not invalidate the icon.
exec /usr/bin/open -a Terminal "$install_root/启动掌问.command"
'''


def default_applications() -> Path:
    shared = Path('/Applications')
    return shared if shared.is_dir() and os.access(shared, os.W_OK) else Path.home() / 'Applications'


def create_app(install_root: Path, applications: Path) -> Path:
    install_root = install_root.resolve()
    if any(c in str(install_root) for c in '\n\r\0') or not (install_root / '启动掌问.command').is_file():
        raise ValueError('A valid installed launch command is required')
    applications = applications.resolve()
    applications.mkdir(parents=True, exist_ok=True)
    app = applications / '掌问.app'
    marker = app / 'Contents/Resources/zhangwen-launcher.json'
    # Never replace another application, even if it has the same display name.
    if app.is_symlink():
        raise ValueError(f'Linked application preserved: {app}')
    if app.exists():
        try:
            if json.loads(marker.read_text(encoding='utf-8')).get('kind') != KIND:
                raise ValueError('Unknown application')
        except (OSError, ValueError, AttributeError):
            raise ValueError(f'Existing application preserved: {app}') from None
    for relative in ['Contents', 'Contents/MacOS', 'Contents/Resources']:
        directory = app / relative
        if directory.is_symlink():
            raise ValueError(f'Linked application directory preserved: {directory}')
        directory.mkdir(parents=True, exist_ok=True)

    def write(relative: str, data: bytes, *, executable: bool = False) -> None:
        file = app / relative
        if file.is_symlink():
            raise ValueError(f'Linked application file preserved: {file}')
        temporary = file.with_name(file.name + '.new-' + uuid.uuid4().hex)
        temporary.write_bytes(data)
        temporary.chmod(0o755 if executable else 0o644)
        temporary.replace(file)

    info = {
        'CFBundleName': '掌问', 'CFBundleDisplayName': '掌问',
        'CFBundleIdentifier': 'cn.zhangwen.local-web', 'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': 'zhangwen', 'CFBundleIconFile': 'palm-logo.icns',
        'CFBundleVersion': '1', 'CFBundleShortVersionString': '0.1.0',
        'LSMinimumSystemVersion': '13.5', 'LSUIElement': True,
        'LSApplicationCategoryType': 'public.app-category.education',
        'NSHighResolutionCapable': True,
    }
    write('Contents/Info.plist', plistlib.dumps(info))
    write('Contents/PkgInfo', b'APPL????')
    write('Contents/MacOS/zhangwen', LAUNCHER.encode(), executable=True)
    write('Contents/Resources/install-root.txt', (str(install_root) + '\n').encode())
    write('Contents/Resources/palm-logo.icns', (ROOT / 'apps/web/src/assets/palm-logo.icns').read_bytes())
    write('Contents/Resources/zhangwen-launcher.json', json.dumps({'kind': KIND, 'version': 1}).encode())
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create the macOS ZhangWen application launcher')
    parser.add_argument('--install-root', required=True, type=Path)
    parser.add_argument('--applications-dir', type=Path, default=None)
    args = parser.parse_args()
    try:
        path = create_app(args.install_root, args.applications_dir or default_applications())
        print(f'Application: {path}')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Could not create the application launcher: {exc}\n')
