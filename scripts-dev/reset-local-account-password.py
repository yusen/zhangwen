from __future__ import annotations

import argparse
import getpass
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LOCAL_API_ROOT = REPOSITORY_ROOT / "services" / "local-api"
sys.path.insert(0, str(LOCAL_API_ROOT))

from zhangwen.auth.repository import AuthError, AuthRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="安全重置掌问旧版本机账号密码；不会修改项目归属。",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=LOCAL_API_ROOT / ".data",
        help="掌问 Sidecar 数据目录；默认使用仓库开发数据目录。",
    )
    parser.add_argument(
        "--username",
        help="要恢复的本机账号；省略时在终端中选择。",
    )
    args = parser.parse_args()
    data_dir = args.data_dir.resolve()
    repository = AuthRepository(data_dir)
    accounts = repository.local_accounts()
    if not accounts:
        print("没有找到可恢复的本机账号。")
        return 2

    print("可恢复的本机账号：")
    for account in accounts:
        print(f"  - {account.username}（{account.displayName}）")
    username = (args.username or input("请输入要恢复的账号：")).strip().lower()
    matched = next((account for account in accounts if account.username.lower() == username), None)
    if matched is None:
        print("输入的账号不在可恢复列表中。")
        return 2

    phrase = input(f"请输入“重置 {matched.username}”继续：").strip()
    if phrase != f"重置 {matched.username}":
        print("确认短语不匹配，未修改任何数据。")
        return 3

    password = getpass.getpass("请输入新密码（8–128 位，包含字母和数字）：")
    confirmation = getpass.getpass("请再次输入新密码：")
    if password != confirmation:
        print("两次密码不一致，未修改任何数据。")
        return 3

    auth_db = data_dir / "auth" / "zhangwen-auth.sqlite3"
    if not auth_db.is_file():
        print(f"认证数据库不存在：{auth_db}")
        return 2
    backup_dir = auth_db.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"zhangwen-auth.{timestamp}.sqlite3.bak"
    with (
        sqlite3.connect(f"file:{auth_db}?mode=ro", uri=True) as source,
        sqlite3.connect(backup_path) as destination,
    ):
        source.backup(destination)

    try:
        repository.reset_local_password(
            username=matched.username,
            new_password=password,
        )
    except AuthError as exc:
        backup_path.unlink(missing_ok=True)
        print(f"重置失败：{exc}")
        return 4
    finally:
        password = ""
        confirmation = ""

    print(f"已重置本机账号：{matched.username}")
    print("该账号的旧登录会话已全部撤销。")
    print(f"认证库备份：{backup_path}")
    print("请重新启动掌问，并选择“本机账号登录”。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
