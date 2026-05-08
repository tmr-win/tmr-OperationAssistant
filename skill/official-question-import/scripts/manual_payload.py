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
    "rawResolutionRule": ("rawResolutionRule", "raw_resolution_rule", "resolutionRule", "resolution_rule"),
    "yesLabel": ("yesLabel", "yes_label"),
    "noLabel": ("noLabel", "no_label"),
    "resolutionRuleNote": ("resolutionRuleNote", "resolution_rule_note"),
    "labelReason": ("labelReason", "label_reason", "reason"),
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


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    text = normalize_text(value).lower()
    return text in {"1", "true", "yes", "y"}


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


def validate_binary_label_pair(
    *,
    yes_label: str,
    no_label: str,
    question_index: int,
) -> None:
    for label_name, label_value in (("yesLabel", yes_label), ("noLabel", no_label)):
        if not label_value:
            continue
        if label_value.lower().startswith("resolves"):
            raise ValueError(f"第 {question_index} 题的 {label_name} 不能以 Resolves 开头")
        if len(label_value) > 52:
            raise ValueError(f"第 {question_index} 题的 {label_name} 超过 52 个字符")


def build_options_from_binary_labels(
    *,
    yes_label: str,
    no_label: str,
    question_index: int,
) -> list[dict[str, str]]:
    if not yes_label or not no_label:
        raise ValueError(f"第 {question_index} 题的 yesLabel 和 noLabel 必须同时提供")
    validate_binary_label_pair(yes_label=yes_label, no_label=no_label, question_index=question_index)
    return [
        {"label": yes_label, "labelEn": yes_label},
        {"label": no_label, "labelEn": no_label},
    ]


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
        "rawResolutionRule": pick_value(raw_question, FIELD_ALIASES["rawResolutionRule"]),
        "yesLabel": pick_value(raw_question, FIELD_ALIASES["yesLabel"]),
        "noLabel": pick_value(raw_question, FIELD_ALIASES["noLabel"]),
        "resolutionRuleNote": pick_value(raw_question, FIELD_ALIASES["resolutionRuleNote"]),
        "needsRuleReview": normalize_bool(raw_question.get("needsRuleReview")),
        "labelReason": pick_value(raw_question, FIELD_ALIASES["labelReason"]),
        "options": [],
    }

    if not normalized["title"]:
        raise ValueError(f"第 {question_index} 题缺少 title")
    if not normalized["titleEn"]:
        raise ValueError(f"第 {question_index} 题缺少 titleEn")
    if not normalized["deadlineAt"]:
        raise ValueError(f"第 {question_index} 题缺少 deadlineAt")

    if normalized["yesLabel"] or normalized["noLabel"]:
        normalized["options"] = build_options_from_binary_labels(
            yes_label=normalized["yesLabel"],
            no_label=normalized["noLabel"],
            question_index=question_index,
        )
    else:
        raw_options = raw_question.get("options")
        if not isinstance(raw_options, list) or len(raw_options) < 2:
            raise ValueError(f"第 {question_index} 题至少需要 2 个 options，或提供 yesLabel / noLabel")
        normalized["options"] = [
            normalize_option(raw_option, question_index, option_index)
            for option_index, raw_option in enumerate(raw_options, start=1)
        ]

    if normalized["yesLabel"] and normalized["noLabel"]:
        validate_binary_label_pair(
            yes_label=normalized["yesLabel"],
            no_label=normalized["noLabel"],
            question_index=question_index,
        )
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
