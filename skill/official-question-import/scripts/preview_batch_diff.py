#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from common import (
    QUESTIONS_FILE_NAME,
    TOOL_TEMPLATE_DIR,
    print_json,
    resolve_batch_candidate,
    resolve_workspace,
    workspace_has_tool_layout,
    write_last_workspace,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace")
    parser.add_argument("--query", required=True)
    parser.add_argument("--json-file", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--preview-all", action="store_true")
    return parser.parse_args()


def ensure_diff_script(workspace: Path) -> Path:
    source = TOOL_TEMPLATE_DIR / "scripts" / "diff-official-questions-json.mjs"
    if not source.exists():
        raise FileNotFoundError(f"未找到 diff 脚本：{source}")

    target = workspace / "scripts" / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def main() -> int:
    args = parse_args()
    workspace = resolve_workspace(args.workspace, require_exists=True)
    if workspace is None:
        print_json({"status": "error", "message": "未找到导题工作目录，请先初始化。"})
        return 1
    if not workspace_has_tool_layout(workspace):
        print_json({"status": "error", "message": f"目录不是有效的导题工作区：{workspace}"})
        return 1

    json_file = Path(args.json_file).expanduser().resolve()
    if not json_file.exists():
        print_json({"status": "error", "message": f"未找到 JSON 文件：{json_file}"})
        return 1

    write_last_workspace(workspace)

    status, candidates = resolve_batch_candidate(workspace, args.query)
    if status == "ambiguous":
        print_json(
            {
                "status": "ambiguous",
                "message": "批次候选不唯一，请先确认。",
                "candidates": [item.to_dict() for item in candidates],
            }
        )
        return 2
    if status != "resolved":
        print_json({"status": "not_found", "message": f"未找到批次：{args.query}"})
        return 3

    batch = candidates[0]
    workbook = batch.path / QUESTIONS_FILE_NAME
    if not workbook.exists():
        print_json({"status": "error", "message": f"未找到题目文件：{workbook}"})
        return 1

    try:
        diff_script = ensure_diff_script(workspace)
    except FileNotFoundError as error:
        print_json({"status": "error", "message": str(error)})
        return 1

    command = [
        "node",
        str(diff_script),
        "--workbook",
        str(workbook),
        "--json-file",
        str(json_file),
    ]
    if args.preview_all:
        command.append("--preview-all")
    else:
        command.extend(["--limit", str(args.limit)])

    result = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )

    payload = None
    stdout = result.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None

    print_json(
        {
            "status": "ok" if result.returncode == 0 else "error",
            "workspace": str(workspace),
            "batch": batch.to_dict(),
            "json_file": str(json_file),
            "command": command,
            "returncode": result.returncode,
            "diff": payload,
            "stdout": stdout,
            "stderr": result.stderr.strip(),
        }
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
