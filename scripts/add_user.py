#!/usr/bin/env python3
"""本地添加 TavernMixer 用户（注册已关闭时使用）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description="添加 TavernMixer 登录账号")
    parser.add_argument("username", help="用户名")
    parser.add_argument("password", help="密码")
    parser.add_argument("--nickname", default="", help="昵称（可选）")
    parser.add_argument("--admin", action="store_true", help="设为管理员")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == args.username).first():
            print(f"错误: 用户名 {args.username!r} 已存在", file=sys.stderr)
            sys.exit(1)
        user = User(
            username=args.username.strip(),
            password_hash=hash_password(args.password),
            nickname=(args.nickname or args.username).strip()[:64],
            is_admin=args.admin,
        )
        db.add(user)
        db.commit()
        print(f"已创建用户: {user.username} (id={user.id}, admin={user.is_admin})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
