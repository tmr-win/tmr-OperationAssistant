#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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
    resolve_batch_candidate,
    resolve_workspace,
    workspace_has_tool_layout,
    write_last_workspace,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace")
    parser.add_argument("--query")
    parser.add_argument("--batch-name")
    parser.add_argument("--topic")
    parser.add_argument("--json-file", required=True)
    parser.add_argument("--mode", choices=["replace", "append"], default="replace")
    return parser.parse_args()


def ensure_batch_dir(workspace: Path, batch_name: str) -> tuple[Path, bool]:
    batch_dir = workspace / BATCH_DIR_NAME / batch_name
    if batch_dir.exists():
        return batch_dir, False

    template_path = workspace / TEMPLATE_DIR_NAME / TEMPLATE_FILE_NAME
    if not template_path.exists():
        raise FileNotFoundError(f"未找到模板文件：{template_path}")

    batch_dir.mkdir(parents=True, exist_ok=False)
    (batch_dir / IMAGES_DIR_NAME).mkdir(parents=True, exist_ok=True)
    shutil.copy2(template_path, batch_dir / QUESTIONS_FILE_NAME)

    notes_source = TOOL_TEMPLATE_DIR / BATCH_DIR_NAME / "_批次模板" / "notes.txt"
    if notes_source.exists():
        shutil.copy2(notes_source, batch_dir / "notes.txt")
    return batch_dir, True


def resolve_target_batch(workspace: Path, args: argparse.Namespace) -> tuple[Path, str, bool]:
    if args.query:
        status, candidates = resolve_batch_candidate(workspace, args.query)
        if status == "ambiguous":
            raise ValueError(
                json.dumps(
                    {
                        "status": "ambiguous",
                        "message": "批次候选不唯一，请先确认。",
                        "candidates": [item.to_dict() for item in candidates],
                    },
                    ensure_ascii=False,
                )
            )
        if status != "resolved":
            raise FileNotFoundError(f"未找到批次：{args.query}")
        batch = candidates[0]
        return batch.path, batch.name, False

    batch_name = args.batch_name or next_batch_name(workspace, args.topic or "manual-text")
    batch_dir, created = ensure_batch_dir(workspace, batch_name)
    return batch_dir, batch_name, created


def ensure_writer_script(workspace: Path) -> Path:
    source = TOOL_TEMPLATE_DIR / "scripts" / "write-official-questions-from-json.mjs"
    if not source.exists():
        raise FileNotFoundError(f"未找到写表脚本：{source}")

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

    try:
        batch_dir, batch_name, is_created = resolve_target_batch(workspace, args)
        writer_script = ensure_writer_script(workspace)
    except ValueError as error:
        payload = str(error)
        try:
            print(payload)
        except Exception:
            print_json({"status": "error", "message": payload})
        return 2
    except FileNotFoundError as error:
        print_json({"status": "error", "message": str(error)})
        return 1

    workbook_path = batch_dir / QUESTIONS_FILE_NAME
    command = [
        "node",
        str(writer_script),
        "--workbook",
        str(workbook_path),
        "--json-file",
        str(json_file),
        "--mode",
        args.mode,
    ]
    result = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )

    writer_payload: dict | None = None
    stdout = result.stdout.strip()
    if stdout:
        try:
            writer_payload = json.loads(stdout)
        except json.JSONDecodeError:
            writer_payload = None

    payload = {
        "status": "ok" if result.returncode == 0 else "error",
        "workspace": str(workspace),
        "batch_name": batch_name,
        "batch_dir": str(batch_dir),
        "questions_file": str(workbook_path),
        "json_file": str(json_file),
        "mode": args.mode,
        "is_created": is_created,
        "command": command,
        "returncode": result.returncode,
        "writer": writer_payload,
        "stdout": stdout,
        "stderr": result.stderr.strip(),
    }
    print_json(payload)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
