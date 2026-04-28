#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "category": ("category", "defaultCategory", "default_category"),
    "sourceUrl": ("sourceUrl", "source_url", "defaultSourceUrl", "default_source_url"),
    "announceAt": ("announceAt", "announce_at", "defaultAnnounceAt", "default_announce_at"),
    "scheduledPublishAt": (
        "scheduledPublishAt",
        "scheduled_publish_at",
        "defaultScheduledPublishAt",
        "default_scheduled_publish_at",
    ),
    "title": ("title",),
    "titleEn": ("titleEn", "title_en"),
    "deadlineAt": ("deadlineAt", "deadline_at"),
    "candidateQuestionId": ("candidateQuestionId", "candidate_question_id"),
    "imageFileName": ("imageFileName", "image_file_name", "imageFile", "image_file"),
}

OPTION_ALIASES: dict[str, tuple[str, ...]] = {
    "label": ("label",),
    "labelEn": ("labelEn", "label_en"),
}


def load_payload(json_file: Path) -> dict[str, Any]:
    payload = json.loads(json_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("payload 顶层必须是对象")
    return payload


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def pick_value(source: dict[str, Any], aliases: tuple[str, ...]) -> str:
    for alias in aliases:
        if alias not in source:
            continue
        text = normalize_text(source.get(alias))
        if text:
            return text
    return ""


def normalize_defaults(raw_defaults: Any) -> dict[str, str]:
    if raw_defaults in (None, ""):
        return {}
    if not isinstance(raw_defaults, dict):
        raise ValueError("defaults 必须是对象")

    normalized: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        if field not in {"title", "titleEn", "deadlineAt", "candidateQuestionId", "imageFileName"}:
            value = pick_value(raw_defaults, aliases)
            if value:
                normalized[field] = value
    return normalized


def normalize_option(raw_option: Any, question_index: int, option_index: int) -> dict[str, str]:
    if not isinstance(raw_option, dict):
        raise ValueError(f"第 {question_index} 题的第 {option_index} 个选项必须是对象")

    option = {
        "label": pick_value(raw_option, OPTION_ALIASES["label"]),
        "labelEn": pick_value(raw_option, OPTION_ALIASES["labelEn"]),
    }
    if not option["label"]:
        raise ValueError(f"第 {question_index} 题的第 {option_index} 个选项缺少 label")
    if not option["labelEn"]:
        raise ValueError(f"第 {question_index} 题的第 {option_index} 个选项缺少 labelEn")
    return option


def normalize_question(raw_question: Any, question_index: int) -> dict[str, Any]:
    if not isinstance(raw_question, dict):
        raise ValueError(f"第 {question_index} 题必须是对象")

    normalized = {
        "title": pick_value(raw_question, FIELD_ALIASES["title"]),
        "titleEn": pick_value(raw_question, FIELD_ALIASES["titleEn"]),
        "category": pick_value(raw_question, FIELD_ALIASES["category"]),
        "sourceUrl": pick_value(raw_question, FIELD_ALIASES["sourceUrl"]),
        "deadlineAt": pick_value(raw_question, FIELD_ALIASES["deadlineAt"]),
        "announceAt": pick_value(raw_question, FIELD_ALIASES["announceAt"]),
        "scheduledPublishAt": pick_value(raw_question, FIELD_ALIASES["scheduledPublishAt"]),
        "candidateQuestionId": pick_value(raw_question, FIELD_ALIASES["candidateQuestionId"]),
        "imageFileName": pick_value(raw_question, FIELD_ALIASES["imageFileName"]),
        "options": [],
    }

    if not normalized["title"]:
        raise ValueError(f"第 {question_index} 题缺少 title")
    if not normalized["titleEn"]:
        raise ValueError(f"第 {question_index} 题缺少 titleEn")
    if not normalized["deadlineAt"]:
        raise ValueError(f"第 {question_index} 题缺少 deadlineAt")

    raw_options = raw_question.get("options")
    if not isinstance(raw_options, list) or len(raw_options) < 2:
        raise ValueError(f"第 {question_index} 题至少需要 2 个 options")

    normalized["options"] = [
        normalize_option(raw_option, question_index, option_index)
        for option_index, raw_option in enumerate(raw_options, start=1)
    ]
    return normalized


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ValueError("questions 必须是非空数组")

    normalized_questions = [
        normalize_question(raw_question, index)
        for index, raw_question in enumerate(raw_questions, start=1)
    ]
    normalized_defaults = normalize_defaults(payload.get("defaults"))

    normalized_payload: dict[str, Any] = {"questions": normalized_questions}
    if normalized_defaults:
        normalized_payload["defaults"] = normalized_defaults
    return normalized_payload


def write_payload(json_file: Path, payload: dict[str, Any]) -> None:
    json_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
