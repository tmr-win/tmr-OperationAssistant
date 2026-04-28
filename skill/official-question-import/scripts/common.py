#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
TOOL_TEMPLATE_DIR = SKILL_DIR / "assets" / "tool-template"
STATE_DIR = SKILL_DIR / ".state"
LAST_WORKSPACE_PATH = STATE_DIR / "last-workspace.txt"
DEFAULT_WORKSPACE = Path.home() / "Desktop" / "ops-import-tool"

BATCH_DIR_NAME = "导题批次"
TEMPLATE_DIR_NAME = "模板区"
REPORT_DIR_NAME = "报告区"
TEMPLATE_FILE_NAME = "official-question-template.xlsx"
QUESTIONS_FILE_NAME = "questions.xlsx"
IMAGES_DIR_NAME = "images"


@dataclass
class BatchCandidate:
    name: str
    path: Path
    updated_at: float

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "path": str(self.path),
            "updated_at": datetime.fromtimestamp(self.updated_at).isoformat(),
        }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def expand_path(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return (Path.cwd() / path).resolve()


def read_last_workspace() -> Path | None:
    if not LAST_WORKSPACE_PATH.exists():
        return None
    content = LAST_WORKSPACE_PATH.read_text(encoding="utf-8").strip()
    if not content:
        return None
    path = Path(content).expanduser()
    if path.exists():
        return path
    return None


def write_last_workspace(path: Path) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LAST_WORKSPACE_PATH.write_text(str(path), encoding="utf-8")


def resolve_workspace(path_text: str | None, require_exists: bool = True) -> Path | None:
    if path_text:
        path = expand_path(path_text)
        if require_exists and not path.exists():
            return None
        return path

    remembered = read_last_workspace()
    if remembered is not None:
        return remembered

    if DEFAULT_WORKSPACE.exists():
        return DEFAULT_WORKSPACE

    if require_exists:
        return None
    return DEFAULT_WORKSPACE


def workspace_has_tool_layout(workspace: Path) -> bool:
    required = [
        workspace / "package.json",
        workspace / "scripts" / "import-official-questions.mjs",
        workspace / BATCH_DIR_NAME,
        workspace / TEMPLATE_DIR_NAME,
        workspace / REPORT_DIR_NAME,
    ]
    return all(item.exists() for item in required)


def batch_root(workspace: Path) -> Path:
    return workspace / BATCH_DIR_NAME


def list_batches(workspace: Path) -> list[BatchCandidate]:
    root = batch_root(workspace)
    if not root.exists():
        return []

    candidates: list[BatchCandidate] = []
    for item in root.iterdir():
        if not item.is_dir():
            continue
        if item.name.startswith(".") or item.name == "_批次模板":
            continue
        candidates.append(
            BatchCandidate(
                name=item.name,
                path=item,
                updated_at=item.stat().st_mtime,
            )
        )
    return sorted(candidates, key=lambda item: item.updated_at, reverse=True)


def today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_query(query: str | None) -> str:
    return (query or "").strip().lower()


def resolve_batch_candidate(workspace: Path, query: str | None) -> tuple[str, list[BatchCandidate]]:
    batches = list_batches(workspace)
    if not batches:
        return "not_found", []

    normalized = normalize_query(query)
    if not normalized or normalized in {"latest", "最新", "最新一批", "latest batch"}:
        return "resolved", [batches[0]]

    if "今天" in normalized or normalized in {"today", "今天那批"}:
        matched = [item for item in batches if item.name.startswith(today_prefix())]
        if len(matched) == 1:
            return "resolved", matched
        if matched:
            return "ambiguous", matched
        return "not_found", []

    exact = [item for item in batches if item.name == query]
    if len(exact) == 1:
        return "resolved", exact

    matched = [item for item in batches if normalized in item.name.lower()]
    if len(matched) == 1:
        return "resolved", matched
    if matched:
        return "ambiguous", matched

    return "not_found", []


def slugify_topic(topic: str | None) -> str:
    normalized = (topic or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", normalized)
    normalized = normalized.strip("-")
    if not normalized:
        return "batch"
    return normalized


def next_batch_name(workspace: Path, topic: str | None) -> str:
    prefix = today_prefix()
    topic_slug = slugify_topic(topic)
    current = list_batches(workspace)
    matched_indexes = []
    pattern = re.compile(rf"^{re.escape(prefix)}-{re.escape(topic_slug)}-(\d+)$")
    for item in current:
        matched = pattern.match(item.name)
        if matched:
            matched_indexes.append(int(matched.group(1)))
    next_index = (max(matched_indexes) + 1) if matched_indexes else 1
    return f"{prefix}-{topic_slug}-{next_index:02d}"
