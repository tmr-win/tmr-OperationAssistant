#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from auth_common import (
    AuthError,
    DEFAULT_IDENTITY_BASE_URL,
    DEFAULT_OPS_ADMIN_BASE_URL,
    ensure_login,
)
from common import (
    BATCH_DIR_NAME,
    IMAGES_DIR_NAME,
    QUESTIONS_FILE_NAME,
    REPORT_DIR_NAME,
    print_json,
    resolve_batch_candidate,
    resolve_workspace,
    write_last_workspace,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["validate", "plan", "submit"])
    parser.add_argument("--workspace")
    parser.add_argument("--query")
    parser.add_argument("--base-url", default=DEFAULT_OPS_ADMIN_BASE_URL)
    parser.add_argument("--identity-base-url", default=DEFAULT_IDENTITY_BASE_URL)
    parser.add_argument("--token", default="")
    parser.add_argument("--confirmed", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = resolve_workspace(args.workspace, require_exists=True)
    if workspace is None:
        print_json({"status": "error", "message": "未找到导题工作目录，请先初始化。"})
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
    questions_file = Path(f"./{BATCH_DIR_NAME}/{batch.name}/{QUESTIONS_FILE_NAME}")
    images_dir = Path(f"./{BATCH_DIR_NAME}/{batch.name}/{IMAGES_DIR_NAME}")
    report_dir = Path(f"./{REPORT_DIR_NAME}")

    command = [
        "npm",
        "run",
        "import:official-questions",
        "--",
        args.action,
        str(questions_file),
    ]

    if args.action == "submit":
        if not args.confirmed:
            print_json(
                {
                    "status": "confirmation_required",
                    "message": "submit 动作必须先确认，再带 --confirmed 执行。",
                    "batch": batch.to_dict(),
                }
            )
            return 4
        command.extend(["--base-url", args.base_url, "--report-dir", str(report_dir)])
        if images_dir.exists():
            command.extend(["--images-dir", str(images_dir)])
        try:
            auth_payload = ensure_login(
                base_url=args.base_url,
                identity_base_url=args.identity_base_url,
                requested_by="official-question-import",
                skill_name="official-question-import",
                token=args.token,
            )
        except AuthError as exc:
            print_json(
                {
                    "status": "error",
                    "message": str(exc),
                    "action": args.action,
                    "workspace": str(workspace),
                    "batch": batch.to_dict(),
                    "auth_error": {
                        "code": exc.code,
                        "http_status": exc.http_status,
                    },
                }
            )
            return 6
        if auth_payload.get("status") != "authenticated":
            print_json(
                {
                    "status": auth_payload.get("status") or "token_required",
                    "message": auth_payload.get("summary") or "请先提供运营后台 token。",
                    "action": args.action,
                    "workspace": str(workspace),
                    "batch": batch.to_dict(),
                    "auth": auth_payload,
                }
            )
            return 5
        command.extend(["--token", str(auth_payload.get("access_token") or "")])

    result = subprocess.run(
        command,
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = {
        "status": "ok" if result.returncode == 0 else "error",
        "action": args.action,
        "workspace": str(workspace),
        "batch": batch.to_dict(),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }
    print_json(payload)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
