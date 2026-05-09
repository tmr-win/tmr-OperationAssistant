#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from common import print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace")
    parser.add_argument("--query")
    parser.add_argument("--batch-name")
    parser.add_argument("--topic")
    parser.add_argument("--json-file", required=True)
    parser.add_argument("--mode", choices=["replace", "append"], default="replace")
    parser.add_argument("--keep-normalized-json", action="store_true")
    parser.add_argument("--preview-limit", type=int, default=0)
    parser.add_argument("--preview-all", action="store_true")
    return parser.parse_args()


def run_command(command: list[str]) -> tuple[int, dict | None, str, str]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    payload = None
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = None
    return result.returncode, payload, stdout, stderr


def build_ingest_command(args: argparse.Namespace, normalized_json_file: Path) -> list[str]:
    command = [
        "python3",
        str(Path(__file__).with_name("ingest_manual_text.py")),
    ]
    if args.workspace:
        command.extend(["--workspace", args.workspace])
    if args.query:
        command.extend(["--query", args.query])
    if args.batch_name:
        command.extend(["--batch-name", args.batch_name])
    if args.topic:
        command.extend(["--topic", args.topic])
    command.extend(["--json-file", str(normalized_json_file), "--mode", args.mode])
    return command


def build_complete_command(source_json_file: Path, completed_json_file: Path) -> list[str]:
    return [
        "python3",
        str(Path(__file__).with_name("complete_manual_payload.py")),
        "--json-file",
        str(source_json_file),
        "--output-json-file",
        str(completed_json_file),
    ]


def build_batch_action_command(action: str, workspace: str, batch_name: str) -> list[str]:
    return [
        "python3",
        str(Path(__file__).with_name("run_batch_action.py")),
        action,
        "--workspace",
        workspace,
        "--query",
        batch_name,
    ]


def build_preview_command(
    workspace: str,
    batch_name: str,
    preview_limit: int,
    preview_all: bool,
) -> list[str]:
    command = [
        "python3",
        str(Path(__file__).with_name("preview_batch_rows.py")),
        "--workspace",
        workspace,
        "--query",
        batch_name,
    ]
    if preview_all:
        command.append("--preview-all")
    elif preview_limit > 0:
        command.extend(["--limit", str(preview_limit)])
    return command


def main() -> int:
    args = parse_args()
    source_json_file = Path(args.json_file).expanduser().resolve()
    if not source_json_file.exists():
        print_json({"status": "error", "message": f"未找到 JSON 文件：{source_json_file}"})
        return 1

    with tempfile.TemporaryDirectory(prefix="official-question-import-") as temp_dir:
        completed_json_file = Path(temp_dir) / "completed-manual-questions.json"
        normalized_json_file = Path(temp_dir) / "normalized-manual-questions.json"
        saved_normalized_json_file = ""
        complete_command = build_complete_command(source_json_file, completed_json_file)
        complete_rc, complete_payload, complete_stdout, complete_stderr = run_command(complete_command)
        if complete_rc != 0:
            print_json(
                {
                    "status": "error",
                    "step": "complete_manual_payload",
                    "command": complete_command,
                    "returncode": complete_rc,
                    "payload": complete_payload,
                    "stdout": complete_stdout,
                    "stderr": complete_stderr,
                }
            )
            return complete_rc

        validate_command = [
            "python3",
            str(Path(__file__).with_name("validate_manual_payload.py")),
            "--json-file",
            str(completed_json_file),
            "--output-json-file",
            str(normalized_json_file),
        ]
        validate_rc, validate_payload, validate_stdout, validate_stderr = run_command(validate_command)
        if validate_rc != 0:
            print_json(
                {
                    "status": "error",
                    "step": "validate_manual_payload",
                    "command": validate_command,
                    "returncode": validate_rc,
                    "payload": validate_payload,
                    "stdout": validate_stdout,
                    "stderr": validate_stderr,
                }
            )
            return validate_rc

        if args.keep_normalized_json:
            keep_file = source_json_file.with_name(f"{source_json_file.stem}.normalized.json")
            keep_file.write_text(normalized_json_file.read_text(encoding="utf-8"), encoding="utf-8")
            saved_normalized_json_file = str(keep_file)

        if isinstance(validate_payload, dict):
            validate_payload["output_json_file"] = saved_normalized_json_file

        ingest_command = build_ingest_command(args, normalized_json_file)
        ingest_rc, ingest_payload, ingest_stdout, ingest_stderr = run_command(ingest_command)
        if ingest_rc != 0 or not ingest_payload or ingest_payload.get("status") != "ok":
            print_json(
                {
                    "status": "error",
                    "step": "ingest_manual_text",
                    "command": ingest_command,
                    "returncode": ingest_rc,
                    "payload": ingest_payload,
                    "stdout": ingest_stdout,
                    "stderr": ingest_stderr,
                }
            )
            return ingest_rc or 1

        workspace = str(ingest_payload["workspace"])
        batch_name = str(ingest_payload["batch_name"])

        action_results: dict[str, dict] = {}
        for action in ("validate", "plan"):
            action_command = build_batch_action_command(action, workspace, batch_name)
            action_rc, action_payload, action_stdout, action_stderr = run_command(action_command)
            action_results[action] = {
                "command": action_command,
                "returncode": action_rc,
                "payload": action_payload,
                "stdout": action_stdout,
                "stderr": action_stderr,
            }
            if action_rc != 0:
                print_json(
                    {
                        "status": "error",
                        "step": action,
                        "workspace": workspace,
                        "batch_name": batch_name,
                        "saved_normalized_json_file": saved_normalized_json_file,
                        "complete": complete_payload,
                        "normalize": validate_payload,
                        "ingest": ingest_payload,
                        "actions": action_results,
                    }
                )
                return action_rc

        preview_result: dict | None = None
        if args.preview_all or args.preview_limit > 0:
            preview_command = build_preview_command(
                workspace=workspace,
                batch_name=batch_name,
                preview_limit=args.preview_limit,
                preview_all=args.preview_all,
            )
            preview_rc, preview_payload, preview_stdout, preview_stderr = run_command(preview_command)
            preview_result = {
                "command": preview_command,
                "returncode": preview_rc,
                "payload": preview_payload,
                "stdout": preview_stdout,
                "stderr": preview_stderr,
            }
            if preview_rc != 0:
                print_json(
                    {
                        "status": "error",
                        "step": "preview",
                        "workspace": workspace,
                        "batch_name": batch_name,
                        "saved_normalized_json_file": saved_normalized_json_file,
                        "complete": complete_payload,
                        "normalize": validate_payload,
                        "ingest": ingest_payload,
                        "actions": action_results,
                        "preview": preview_result,
                    }
                )
                return preview_rc

        print_json(
            {
                "status": "ok",
                "workspace": workspace,
                "batch_name": batch_name,
                "saved_normalized_json_file": saved_normalized_json_file,
                "complete": complete_payload,
                "normalize": validate_payload,
                "ingest": ingest_payload,
                "actions": action_results,
                "preview": preview_result,
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
