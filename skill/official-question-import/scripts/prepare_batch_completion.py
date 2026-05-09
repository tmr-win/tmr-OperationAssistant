#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from common import print_json, resolve_workspace


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出批次 workbook 为补全用 JSON，并统计缺失字段。")
    parser.add_argument("--workspace")
    parser.add_argument("--query", required=True)
    parser.add_argument("--output-json-file", default="")
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


def build_missing_fields(question: dict) -> list[str]:
    missing_fields: list[str] = []
    title = str(question.get("title") or "").strip()
    title_en = str(question.get("titleEn") or "").strip()
    deadline_at = str(question.get("deadlineAt") or "").strip()
    announce_at = str(question.get("announceAt") or "").strip()
    scheduled_publish_at = str(question.get("scheduledPublishAt") or "").strip()
    options = question.get("options")
    has_binary_labels = bool(str(question.get("yesLabel") or "").strip()) and bool(
        str(question.get("noLabel") or "").strip()
    )

    if not title and not title_en:
        missing_fields.append("question_stem")
    elif not title or not title_en:
        missing_fields.append("bilingual_title")

    if not deadline_at:
        missing_fields.append("deadlineAt")
    if not announce_at:
        missing_fields.append("announceAt")
    if not scheduled_publish_at:
        missing_fields.append("scheduledPublishAt")

    if not has_binary_labels:
        if not isinstance(options, list) or len(options) < 2:
            missing_fields.append("options")

    return missing_fields


def summarize_questions(questions: list[dict]) -> tuple[dict[str, int], list[dict]]:
    summary = {
        "question_count": len(questions),
        "rows_with_missing_fields": 0,
        "missing_question_stem": 0,
        "missing_bilingual_title": 0,
        "missing_deadline_at": 0,
        "missing_announce_at": 0,
        "missing_scheduled_publish_at": 0,
        "missing_options": 0,
    }
    rows: list[dict] = []

    for index, question in enumerate(questions, start=1):
        missing_fields = build_missing_fields(question)
        if not missing_fields:
            continue

        summary["rows_with_missing_fields"] += 1
        if "question_stem" in missing_fields:
            summary["missing_question_stem"] += 1
        if "bilingual_title" in missing_fields:
            summary["missing_bilingual_title"] += 1
        if "deadlineAt" in missing_fields:
            summary["missing_deadline_at"] += 1
        if "announceAt" in missing_fields:
            summary["missing_announce_at"] += 1
        if "scheduledPublishAt" in missing_fields:
            summary["missing_scheduled_publish_at"] += 1
        if "options" in missing_fields:
            summary["missing_options"] += 1

        rows.append(
            {
                "row_number": index + 1,
                "title": str(question.get("title") or "").strip(),
                "titleEn": str(question.get("titleEn") or "").strip(),
                "missing_fields": missing_fields,
            }
        )

    return summary, rows


def main() -> int:
    args = parse_args()
    workspace = resolve_workspace(args.workspace, require_exists=True)
    if workspace is None:
        print_json({"status": "error", "message": "未找到导题工作目录，请先初始化。"})
        return 1

    output_json_file = args.output_json_file.strip()
    if output_json_file:
        output_path = Path(output_json_file).expanduser().resolve()
    else:
        output_path = workspace / "tmp" / "batch-completion-source.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "python3",
        str(Path(__file__).with_name("export_batch_to_json.py")),
        "--workspace",
        str(workspace),
        "--query",
        args.query,
        "--output-json-file",
        str(output_path),
    ]
    returncode, payload, stdout, stderr = run_command(command)
    if returncode != 0 or not isinstance(payload, dict):
        print_json(
            {
                "status": "error",
                "step": "export_batch_to_json",
                "command": command,
                "returncode": returncode,
                "payload": payload,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        return returncode or 1

    export_payload = payload.get("export") or {}
    workbook_payload = export_payload.get("payload") or {}
    questions = workbook_payload.get("questions") or []
    if not isinstance(questions, list):
        print_json(
            {
                "status": "error",
                "message": "导出的 payload.questions 不是数组",
                "command": command,
                "payload": payload,
            }
        )
        return 1

    summary, rows = summarize_questions(questions)
    print_json(
        {
            "status": "ok",
            "workspace": str(workspace),
            "query": args.query,
            "output_json_file": str(output_path),
            "summary": summary,
            "rows": rows,
            "next_step": "让 Agent 基于 output_json_file 自动补全缺失字段，再用 run_conversation_import --query <批次> --json-file <补全后的 JSON> --mode replace 回写 workbook。",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
