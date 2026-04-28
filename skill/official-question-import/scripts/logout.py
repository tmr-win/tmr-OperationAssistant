#!/usr/bin/env python3
from __future__ import annotations

import argparse

from auth_common import clear_local_state
from common import print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="清理 official-question-import 的本地运营后台登录态。")
    parser.add_argument("--base-url", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = clear_local_state(base_url=args.base_url)
    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
