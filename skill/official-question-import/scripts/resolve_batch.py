#!/usr/bin/env python3
from __future__ import annotations

import sys

from common import print_json, resolve_batch_candidate, resolve_workspace, write_last_workspace


def parse_args(argv: list[str]) -> tuple[str | None, str | None]:
    workspace = None
    query = None
    index = 0
    while index < len(argv):
        key = argv[index]
        if key == "--workspace":
            workspace = argv[index + 1]
            index += 2
            continue
        if key == "--query":
            query = argv[index + 1]
            index += 2
            continue
        raise SystemExit(f"不支持的参数：{key}")
    return workspace, query


def main() -> int:
    workspace_arg, query = parse_args(sys.argv[1:])
    workspace = resolve_workspace(workspace_arg, require_exists=True)
    if workspace is None:
        print_json({"status": "error", "message": "未找到导题工作目录，请先初始化。"})
        return 1

    write_last_workspace(workspace)

    status, candidates = resolve_batch_candidate(workspace, query)
    if status == "resolved":
        print_json(
            {
                "status": "resolved",
                "workspace": str(workspace),
                "batch": candidates[0].to_dict(),
            }
        )
        return 0

    if status == "ambiguous":
        print_json(
            {
                "status": "ambiguous",
                "workspace": str(workspace),
                "candidates": [item.to_dict() for item in candidates],
            }
        )
        return 2

    print_json(
        {
            "status": "not_found",
            "workspace": str(workspace),
            "query": query,
        }
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
