"""Create a small macOS launcher for the local Web service; no native app runtime."""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIND = 'zhangwen-local-web-launcher'
LAUNCHER = '''#!/bin/bash
set -euo pipefail
resources=$(cd "$(dirname "$0")/../Resources" && pwd)
install_root=$(cat "$resources/install-root.txt")
# Resolve the selected runtime on every click, without opening Terminal first.
revision=$(cat "$install_root/current.txt")
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || exit 1
python="$install_root/versions/$revision/.venv/bin/python"
if [ ! -x "$python" ]; then
  /usr/bin/osascript -e 'display alert "掌问启动提示" message "Python环境不可用，请重新运行安装命令修复。"'
  exit 1
fi
exec "$python" "$resources/launch-macos.py" --install-root "$install_root"
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
        'CFBundleVersion': '2', 'CFBundleShortVersionString': '0.1.0',
        'LSMinimumSystemVersion': '13.5', 'LSUIElement': True,
        'LSApplicationCategoryType': 'public.app-category.education',
        'NSHighResolutionCapable': True,
    }
    write('Contents/Info.plist', plistlib.dumps(info))
    write('Contents/PkgInfo', b'APPL????')
    write('Contents/MacOS/zhangwen', LAUNCHER.encode(), executable=True)
    write('Contents/Resources/install-root.txt', (str(install_root) + '\n').encode())
    write('Contents/Resources/launch-macos.py', (ROOT / 'scripts/launch-macos.py').read_bytes())
    write('Contents/Resources/palm-logo.icns', (ROOT / 'apps/web/src/assets/palm-logo.icns').read_bytes())
    write('Contents/Resources/zhangwen-launcher.json', json.dumps({'kind': KIND, 'version': 2}).encode())
    return app


def repair_managed_app(version: Path, applications: Path | None = None) -> Path | None:
    """An old installer may have selected this version without creating its app.

    Only the selected managed installation can repair a launcher at startup;
    source checkouts and prepare-only/new-version setup must not change it.
    """
    version = version.resolve()
    if version.parent.name != 'versions' or not re.fullmatch(r'[0-9a-f]{40}', version.name):
        return None
    install_root = version.parent.parent
    try:
        if (install_root / 'current.txt').read_text(encoding='utf-8').strip() != version.name:
            return None
    except OSError:
        return None
    if applications is None:
        # Keep an existing managed app in its original shared/personal folder.
        for directory in [Path('/Applications'), Path.home() / 'Applications']:
            marker = directory / '掌问.app/Contents/Resources/install-root.txt'
            try:
                if marker.read_text(encoding='utf-8').strip() == str(install_root):
                    applications = directory
                    break
            except OSError:
                pass
    return create_app(install_root, applications or default_applications())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create the macOS ZhangWen application launcher')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--install-root', type=Path)
    action.add_argument('--repair-managed', action='store_true')
    parser.add_argument('--applications-dir', type=Path, default=None)
    args = parser.parse_args()
    try:
        path = (repair_managed_app(ROOT, args.applications_dir) if args.repair_managed
                else create_app(args.install_root, args.applications_dir or default_applications()))
        if path is not None:
            print(f'Application: {path}')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Could not create the application launcher: {exc}\n')
