#!/usr/bin/env python3
from __future__ import annotations

import argparse

from auth_common import AuthError, ensure_login
from common import print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="确保 official-question-import 的运营后台登录态可用。")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--identity-base-url", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--email", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--requested-by", default="official-question-import")
    parser.add_argument("--skill-name", default="official-question-import")
    parser.add_argument("--force-rebind", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = ensure_login(
            base_url=args.base_url,
            identity_base_url=args.identity_base_url,
            requested_by=args.requested_by,
            skill_name=args.skill_name,
            force_rebind=args.force_rebind,
            token=args.token,
            email=args.email,
            password=args.password,
        )
    except AuthError as exc:
        print_json(
            {
                "status": "error",
                "message": str(exc),
                "auth_error": {
                    "code": exc.code,
                    "http_status": exc.http_status,
                },
            }
        )
        return 1
    print_json(payload)
    if payload.get("status") == "authenticated":
        return 0
    if payload.get("status") == "credentials_required":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
