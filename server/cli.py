"""服务器初始化与管理员维护命令。"""

from __future__ import annotations

import argparse
import getpass

from sqlalchemy import select

from .config import Settings
from .database import Database
from .models import Admin
from .security import PasswordService, generate_master_key


def main() -> int:
    parser = argparse.ArgumentParser(description="SWU 新生打卡控制台管理")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("generate-key", help="生成 AES-256 主密钥")
    subparsers.add_parser("init-db", help="创建数据库表")
    create_admin = subparsers.add_parser("create-admin", help="创建或更新管理员")
    create_admin.add_argument("username")
    args = parser.parse_args()

    if args.command == "generate-key":
        print(generate_master_key())
        return 0

    settings = Settings.from_env()
    database = Database(settings.database_url)
    database.create_all()
    if args.command == "init-db":
        print("数据库已初始化")
        return 0

    password = getpass.getpass("管理员密码: ")
    confirmation = getpass.getpass("再次输入: ")
    if len(password) < 12:
        raise SystemExit("管理员密码至少需要 12 位")
    if password != confirmation:
        raise SystemExit("两次密码不一致")
    with database.session() as session:
        admin = session.scalar(select(Admin).where(Admin.username == args.username))
        password_hash = PasswordService().hash(password)
        if admin is None:
            session.add(Admin(username=args.username, password_hash=password_hash))
        else:
            admin.password_hash = password_hash
            admin.disabled = False
        session.commit()
    print("管理员已保存")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
