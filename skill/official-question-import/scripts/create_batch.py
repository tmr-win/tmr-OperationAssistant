#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from common import (
    BATCH_DIR_NAME,
    IMAGES_DIR_NAME,
    QUESTIONS_FILE_NAME,
    TEMPLATE_DIR_NAME,
    TEMPLATE_FILE_NAME,
    TOOL_TEMPLATE_DIR,
    next_batch_name,
    print_json,
    resolve_workspace,
    write_last_workspace,
)


def parse_args(argv: list[str]) -> tuple[str | None, str | None, str | None]:
    workspace = None
    name = None
    topic = None
    index = 0
    while index < len(argv):
        key = argv[index]
        if key == "--workspace":
            workspace = argv[index + 1]
            index += 2
            continue
        if key == "--name":
            name = argv[index + 1]
            index += 2
            continue
        if key == "--topic":
            topic = argv[index + 1]
            index += 2
            continue
        raise SystemExit(f"不支持的参数：{key}")
    return workspace, name, topic


def main() -> int:
    workspace_arg, name, topic = parse_args(sys.argv[1:])
    workspace = resolve_workspace(workspace_arg, require_exists=True)
    if workspace is None:
        print_json({"status": "error", "message": "未找到导题工作目录，请先初始化。"})
        return 1

    write_last_workspace(workspace)

    batch_name = name or next_batch_name(workspace, topic)
    batch_dir = workspace / BATCH_DIR_NAME / batch_name
    if batch_dir.exists():
        print_json({"status": "error", "message": f"批次目录已存在：{batch_dir}"})
        return 1

    template_path = workspace / TEMPLATE_DIR_NAME / TEMPLATE_FILE_NAME
    if not template_path.exists():
        print_json({"status": "error", "message": f"未找到模板文件：{template_path}"})
        return 1

    batch_dir.mkdir(parents=True, exist_ok=False)
    (batch_dir / IMAGES_DIR_NAME).mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, batch_dir / QUESTIONS_FILE_NAME)
    shutil.copy2(
        TOOL_TEMPLATE_DIR / BATCH_DIR_NAME / "_批次模板" / "notes.txt",
        batch_dir / "notes.txt",
    )

    print_json(
        {
            "status": "ok",
            "workspace": str(workspace),
            "batch_name": batch_name,
            "batch_dir": str(batch_dir),
            "questions_file": str(batch_dir / QUESTIONS_FILE_NAME),
            "images_dir": str(batch_dir / IMAGES_DIR_NAME),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
