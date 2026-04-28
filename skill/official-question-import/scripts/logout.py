#!/usr/bin/env python3
from __future__ import annotations

import argparse

from auth_common import AuthError, clear_local_state
from common import print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理 official-question-import 的本地运营后台登录态。")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--identity-base-url", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = clear_local_state(base_url=args.base_url, identity_base_url=args.identity_base_url)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
