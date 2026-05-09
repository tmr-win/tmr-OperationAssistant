#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from common import print_json
from manual_payload import FIELD_ALIASES, load_payload, normalize_payload, write_payload


AMERICA_NEW_YORK = ZoneInfo("America/New_York")
DEFAULT_COMPLETION_MODEL = "gpt-4.1-mini"
OFFICIAL_CATEGORIES = (
    "政治",
    "体育",
    "加密货币",
    "电竞游戏",
    "金融",
    "科技",
    "流行文化",
)
CATEGORY_ALIAS_TO_ZH = {
    "政治": "政治",
    "时事": "政治",
    "politics": "政治",
    "politic": "政治",
    "current affairs": "政治",
    "news": "政治",
    "elections": "政治",
    "体育": "体育",
    "sport": "体育",
    "sports": "体育",
    "加密": "加密货币",
    "加密货币": "加密货币",
    "crypto": "加密货币",
    "cryptocurrency": "加密货币",
    "web3": "加密货币",
    "游戏": "电竞游戏",
    "电竞": "电竞游戏",
    "电竞游戏": "电竞游戏",
    "esports": "电竞游戏",
    "e-sports": "电竞游戏",
    "esport": "电竞游戏",
    "gaming": "电竞游戏",
    "games": "电竞游戏",
    "金融": "金融",
    "财经": "金融",
    "finance": "金融",
    "business": "金融",
    "科技": "科技",
    "tech": "科技",
    "technology": "科技",
    "ai": "科技",
    "artificial intelligence": "科技",
    "流行文化": "流行文化",
    "泛娱乐": "流行文化",
    "娱乐": "流行文化",
    "pop culture": "流行文化",
    "popular culture": "流行文化",
    "entertainment": "流行文化",
    "culture": "流行文化",
}
CRYPTO_KEYWORDS = {
    "btc",
    "bitcoin",
    "eth",
    "ethereum",
    "sol",
    "solana",
    "xrp",
    "doge",
    "hype",
    "hyperliquid",
    "bnb",
    "ton",
    "sui",
    "ada",
    "trx",
    "avax",
    "dot",
    "link",
    "wif",
    "pepe",
    "bonk",
}
SPORTS_KEYWORDS = {
    "vs",
    "match",
    "game",
    "fixture",
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "epl",
    "uefa",
    "fifa",
    "tennis",
    "baseball",
    "basketball",
    "football",
    "soccer",
    "hockey",
    "cricket",
    "lakers",
    "warriors",
    "arsenal",
    "chelsea",
    "real madrid",
    "barcelona",
}
ESPORTS_KEYWORDS = {
    "valorant",
    "league of legends",
    "lol",
    "dota",
    "counter-strike",
    "cs2",
    "cs:go",
    "overwatch",
    "pubg",
}
POLITICS_KEYWORDS = {
    "president",
    "election",
    "parliament",
    "congress",
    "senate",
    "prime minister",
    "总统",
    "选举",
    "议会",
    "国会",
}
TECH_KEYWORDS = {
    "openai",
    "google",
    "apple",
    "meta",
    "microsoft",
    "tesla",
    "nvidia",
    "huawei",
    "iphone",
    "pura",
    "ai",
    "model",
    "发布会",
    "发布",
    "科技",
}
POP_CULTURE_KEYWORDS = {
    "movie",
    "film",
    "box office",
    "album",
    "song",
    "concert",
    "celebrity",
    "tv",
    "anime",
    "票房",
    "电影",
    "专辑",
    "演唱会",
    "明星",
}
MONTH_TO_NUMBER = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


@dataclass
class CompletionConfig:
    api_key: str
    base_url: str
    model: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="自动补全官方题 payload 中缺失的双语题干、选项和时间字段。")
    parser.add_argument("--json-file", required=True)
    parser.add_argument("--output-json-file")
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def pick_value(source: dict[str, Any], field: str) -> str:
    aliases = FIELD_ALIASES[field]
    for alias in aliases:
        if alias not in source:
            continue
        text = normalize_text(source.get(alias))
        if text:
            return text
    return ""


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def now_in_new_york() -> datetime:
    return datetime.now(AMERICA_NEW_YORK)


def format_local_datetime(value: datetime) -> str:
    return value.astimezone(AMERICA_NEW_YORK).strftime("%Y-%m-%d %H:%M")


def normalize_category(value: str) -> str:
    normalized = value.strip().lower()
    return CATEGORY_ALIAS_TO_ZH.get(normalized, value.strip())


def infer_category_from_text(*texts: str) -> str:
    joined = " ".join(texts).lower()
    if any(keyword in joined for keyword in CRYPTO_KEYWORDS):
        return "加密货币"
    if any(keyword in joined for keyword in ESPORTS_KEYWORDS):
        return "电竞游戏"
    if any(keyword in joined for keyword in SPORTS_KEYWORDS):
        return "体育"
    if any(keyword in joined for keyword in POLITICS_KEYWORDS):
        return "政治"
    if any(keyword in joined for keyword in TECH_KEYWORDS):
        return "科技"
    if any(keyword in joined for keyword in POP_CULTURE_KEYWORDS):
        return "流行文化"
    return "金融"


def parse_clock_token(token: str) -> tuple[int, int]:
    normalized = token.strip().lower().replace(" ", "")
    matched = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", normalized)
    if not matched:
        raise ValueError(f"无法解析时间：{token}")
    hour = int(matched.group(1))
    minute = int(matched.group(2) or "00")
    suffix = matched.group(3)
    if suffix == "am":
        hour = 0 if hour == 12 else hour
    elif suffix == "pm":
        hour = 12 if hour == 12 else hour + 12
    return hour, minute


def build_et_datetime(*, year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=AMERICA_NEW_YORK)


def parse_english_window(title: str) -> tuple[datetime, datetime] | None:
    matched = re.search(
        r"(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:,\s*(?P<year>\d{4}))?,?\s+"
        r"(?P<start>\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*[-–]\s*"
        r"(?P<end>\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)\s*(?:ET|EST|EDT)\b",
        title,
        flags=re.IGNORECASE,
    )
    if not matched:
        return None
    month_token = matched.group("month").lower()
    month = MONTH_TO_NUMBER.get(month_token)
    if month is None:
        return None
    day = int(matched.group("day"))
    year = int(matched.group("year") or now_in_new_york().year)
    start_hour, start_minute = parse_clock_token(matched.group("start"))
    end_hour, end_minute = parse_clock_token(matched.group("end"))
    start_at = build_et_datetime(
        year=year,
        month=month,
        day=day,
        hour=start_hour,
        minute=start_minute,
    )
    end_at = build_et_datetime(
        year=year,
        month=month,
        day=day,
        hour=end_hour,
        minute=end_minute,
    )
    if end_at <= start_at:
        end_at += timedelta(days=1)
    return start_at, end_at


def parse_chinese_window(title: str) -> tuple[datetime, datetime] | None:
    matched = re.search(
        r"(?:(?P<year>\d{4})年)?(?P<month>\d{1,2})月(?P<day>\d{1,2})日\s*"
        r"(?P<start>\d{1,2}:\d{2})\s*[-–]\s*(?P<end>\d{1,2}:\d{2})",
        title,
    )
    if not matched:
        return None
    year = int(matched.group("year") or now_in_new_york().year)
    month = int(matched.group("month"))
    day = int(matched.group("day"))
    start_hour, start_minute = parse_clock_token(matched.group("start"))
    end_hour, end_minute = parse_clock_token(matched.group("end"))
    start_at = build_et_datetime(
        year=year,
        month=month,
        day=day,
        hour=start_hour,
        minute=start_minute,
    )
    end_at = build_et_datetime(
        year=year,
        month=month,
        day=day,
        hour=end_hour,
        minute=end_minute,
    )
    if end_at <= start_at:
        end_at += timedelta(days=1)
    return start_at, end_at


def parse_window_from_titles(title: str, title_en: str) -> tuple[datetime, datetime] | None:
    return (
        parse_english_window(title_en)
        or parse_english_window(title)
        or parse_chinese_window(title)
        or parse_chinese_window(title_en)
    )


def detect_up_down_asset(title: str) -> str:
    matched = re.match(r"\s*(.+?)\s+Up\s+or\s+Down\b", title, flags=re.IGNORECASE)
    if matched:
        return matched.group(1).strip()
    matched = re.match(r"\s*(.+?)\s*[涨跌升降上下]+\b", title)
    if matched:
        return matched.group(1).strip()
    return ""


def build_up_down_titles(asset: str, start_at: datetime, end_at: datetime) -> tuple[str, str]:
    display_asset = asset.strip() or "该标的"
    chinese = (
        f"{display_asset}在美东时间{start_at.month}月{start_at.day}日"
        f"{start_at.strftime('%-H:%M')}-{end_at.strftime('%-H:%M')}这段时间内收盘价会高于开盘价吗？"
    )
    english = (
        f"Will {display_asset} close higher than its opening price during the "
        f"{start_at.strftime('%b %-d %-I:%M%p')}–{end_at.strftime('%-I:%M%p')} ET window?"
    )
    return chinese, english


def infer_yes_no_from_threshold(title: str) -> tuple[str, str] | None:
    normalized = " ".join(title.split())
    english_patterns = [
        r"higher than (?P<value>[^?]+)",
        r"above (?P<value>[^?]+)",
        r"over (?P<value>[^?]+)",
        r"greater than (?P<value>[^?]+)",
        r"close above (?P<value>[^?]+)",
    ]
    for pattern in english_patterns:
        matched = re.search(pattern, normalized, flags=re.IGNORECASE)
        if matched:
            value = matched.group("value").strip(" .?")
            return f"> {value}", f"≤ {value}"
    chinese_patterns = [
        r"高于(?P<value>[^？?]+)",
        r"超过(?P<value>[^？?]+)",
        r"大于(?P<value>[^？?]+)",
    ]
    for pattern in chinese_patterns:
        matched = re.search(pattern, normalized)
        if matched:
            value = matched.group("value").strip(" 。？?")
            return f"> {value}", f"≤ {value}"
    return None


def is_binary_question(title: str, title_en: str) -> bool:
    combined = f"{title} {title_en}".lower()
    return (
        "?" in combined
        or "？" in combined
        or "will " in combined
        or "是否" in combined
        or "会不会" in combined
        or "up or down" in combined
    )


def default_publish_at(deadline_at: datetime) -> datetime:
    candidate = deadline_at - timedelta(days=1)
    midnight = build_et_datetime(
        year=candidate.year,
        month=candidate.month,
        day=candidate.day,
        hour=0,
        minute=0,
    )
    return midnight if midnight < deadline_at else candidate


def default_announce_at(deadline_at: datetime) -> datetime:
    return deadline_at + timedelta(hours=2)


def build_missing_fields(question: dict[str, Any], defaults: dict[str, Any]) -> list[str]:
    missing_fields: list[str] = []
    title = normalize_text(question.get("title"))
    title_en = normalize_text(question.get("titleEn"))
    category = normalize_text(question.get("category")) or normalize_text(defaults.get("category"))
    deadline_at = normalize_text(question.get("deadlineAt"))
    announce_at = normalize_text(question.get("announceAt")) or normalize_text(defaults.get("announceAt"))
    scheduled_publish_at = normalize_text(question.get("scheduledPublishAt")) or normalize_text(
        defaults.get("scheduledPublishAt")
    )
    options = question.get("options")
    yes_label = normalize_text(question.get("yesLabel"))
    no_label = normalize_text(question.get("noLabel"))

    if not title and not title_en:
        missing_fields.append("question_stem")
    if not title:
        missing_fields.append("title")
    if not title_en:
        missing_fields.append("titleEn")
    if not category:
        missing_fields.append("category")
    if not deadline_at:
        missing_fields.append("deadlineAt")
    if not announce_at:
        missing_fields.append("announceAt")
    if not scheduled_publish_at:
        missing_fields.append("scheduledPublishAt")

    if not (yes_label and no_label):
        if not isinstance(options, list) or len(options) < 2:
            missing_fields.append("options")
    return missing_fields


def maybe_get_completion_config() -> CompletionConfig | None:
    api_key = (
        os.getenv("OFFICIAL_QUESTION_IMPORT_LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ZHIPU_LLM_API_KEY")
    )
    if not api_key:
        return None
    base_url = (
        os.getenv("OFFICIAL_QUESTION_IMPORT_LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("ZHIPU_LLM_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = (
        os.getenv("OFFICIAL_QUESTION_IMPORT_LLM_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("ZHIPU_LLM_MODEL")
        or DEFAULT_COMPLETION_MODEL
    )
    return CompletionConfig(api_key=api_key, base_url=base_url, model=model)


def build_completion_prompt(questions: list[dict[str, Any]]) -> str:
    return json.dumps(
        {
            "task": "complete_official_question_fields",
            "rules": {
                "timezone": "America/New_York",
                "allowed_categories": list(OFFICIAL_CATEGORIES),
                "binary_label_policy": [
                    "Prefer concise direct complements.",
                    "Do not start with Resolves.",
                    "Max 52 chars each.",
                    "If no better concise pair is possible, use YES and NO.",
                ],
                "time_policy": [
                    "If an explicit event window is present in the title, use it.",
                    "For sports-like events with explicit start time, deadline is usually 1 hour before start and announce is around expected end time.",
                    "For non-sports questions without exact event time, scheduledPublishAt must be at least 1 day before deadlineAt, and announceAt at least 2 hours after deadlineAt.",
                    "Do not fabricate web-verified schedules. Only infer from the provided text.",
                ],
                "translation_policy": [
                    "If one language title is missing, generate the missing language title.",
                    "Keep the meaning tight and operational. Do not add new claims.",
                ],
            },
            "current_time_et": now_in_new_york().isoformat(),
            "output_schema": {
                "questions": [
                    {
                        "index": 1,
                        "title": "",
                        "titleEn": "",
                        "category": "",
                        "deadlineAt": "",
                        "announceAt": "",
                        "scheduledPublishAt": "",
                        "yesLabel": "",
                        "noLabel": "",
                        "rawResolutionRule": "",
                        "resolutionRuleNote": "",
                        "needsRuleReview": False,
                        "labelReason": "",
                        "completionNote": "",
                    }
                ]
            },
            "questions": questions,
        },
        ensure_ascii=False,
    )


def http_post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    ssl_context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=60, context=ssl_context) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body


def call_llm_completion(config: CompletionConfig, questions: list[dict[str, Any]]) -> dict[str, Any]:
    url = f"{config.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    base_payload = {
        "model": config.model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You complete missing fields for tmr.win official prediction question payloads. "
                    "Return JSON only."
                ),
            },
            {
                "role": "user",
                "content": build_completion_prompt(questions),
            },
        ],
    }
    status_code, body = http_post_json(
        url,
        headers,
        {**base_payload, "response_format": {"type": "json_object"}},
    )
    if status_code >= 400 and "response_format" in body and "not supported" in body.lower():
        status_code, body = http_post_json(url, headers, base_payload)
    if status_code >= 400:
        raise ValueError(f"LLM 补全请求失败：HTTP {status_code} {body[:300]}")
    payload = json.loads(body)
    content = payload["choices"][0]["message"]["content"]
    return json.loads(content)


def apply_deterministic_completion(question: dict[str, Any], defaults: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    completed = dict(question)
    notes: list[str] = []
    title = normalize_text(completed.get("title"))
    title_en = normalize_text(completed.get("titleEn"))
    if not completed.get("category"):
        completed["category"] = infer_category_from_text(title, title_en)

    window = parse_window_from_titles(title, title_en)
    asset = detect_up_down_asset(title_en or title)
    if window and ("up or down" in (title_en or title).lower() or "高于开盘价" in title or "涨跌" in title):
        start_at, end_at = window
        generated_title, generated_title_en = build_up_down_titles(asset, start_at, end_at)
        if not title:
            completed["title"] = generated_title
            notes.append("根据时间窗口模式生成中文题目")
        if not title_en:
            completed["titleEn"] = generated_title_en
            notes.append("根据时间窗口模式生成英文题目")
        if not completed.get("yesLabel") and not completed.get("noLabel") and not completed.get("options"):
            completed["yesLabel"] = "UP"
            completed["noLabel"] = "DOWN"
            notes.append("根据涨跌窗口模式生成 UP/DOWN 选项")
        if not completed.get("deadlineAt"):
            completed["deadlineAt"] = format_local_datetime(end_at)
            notes.append("根据时间窗口生成截止时间")
        if not completed.get("announceAt") and not defaults.get("announceAt"):
            completed["announceAt"] = format_local_datetime(end_at + timedelta(hours=2))
            notes.append("根据时间窗口生成开奖时间")
        if not completed.get("scheduledPublishAt") and not defaults.get("scheduledPublishAt"):
            completed["scheduledPublishAt"] = format_local_datetime(default_publish_at(end_at))
            notes.append("根据时间窗口生成发布时间")

    threshold_pair = infer_yes_no_from_threshold(title_en or title)
    if threshold_pair and not completed.get("yesLabel") and not completed.get("noLabel") and not completed.get("options"):
        completed["yesLabel"], completed["noLabel"] = threshold_pair
        notes.append("根据阈值型题干生成二元标签")

    if is_binary_question(title, title_en) and not completed.get("yesLabel") and not completed.get("noLabel") and not completed.get("options"):
        completed["yesLabel"] = "YES"
        completed["noLabel"] = "NO"
        notes.append("使用通用 YES/NO 作为二元标签兜底")

    deadline_text = normalize_text(completed.get("deadlineAt"))
    if deadline_text:
        deadline_at = datetime.strptime(deadline_text, "%Y-%m-%d %H:%M").replace(tzinfo=AMERICA_NEW_YORK)
        if not completed.get("announceAt") and not defaults.get("announceAt"):
            completed["announceAt"] = format_local_datetime(default_announce_at(deadline_at))
            notes.append("根据截止时间补开奖时间")
        if not completed.get("scheduledPublishAt") and not defaults.get("scheduledPublishAt"):
            completed["scheduledPublishAt"] = format_local_datetime(default_publish_at(deadline_at))
            notes.append("根据截止时间补发布时间")

    if completed.get("category"):
        completed["category"] = normalize_category(normalize_text(completed.get("category")))

    return completed, notes


def apply_llm_completion(
    questions: list[dict[str, Any]],
    defaults: dict[str, Any],
    completion_config: CompletionConfig | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if completion_config is None:
        return questions, []

    unresolved_payload: list[dict[str, Any]] = []
    question_index_map: dict[int, int] = {}
    for index, question in enumerate(questions):
        missing_fields = build_missing_fields(question, defaults)
        if not missing_fields:
            continue
        question_index_map[index + 1] = index
        unresolved_payload.append(
            {
                "index": index + 1,
                "title": normalize_text(question.get("title")),
                "titleEn": normalize_text(question.get("titleEn")),
                "category": normalize_text(question.get("category")) or normalize_text(defaults.get("category")),
                "deadlineAt": normalize_text(question.get("deadlineAt")),
                "announceAt": normalize_text(question.get("announceAt")) or normalize_text(defaults.get("announceAt")),
                "scheduledPublishAt": normalize_text(question.get("scheduledPublishAt"))
                or normalize_text(defaults.get("scheduledPublishAt")),
                "yesLabel": normalize_text(question.get("yesLabel")),
                "noLabel": normalize_text(question.get("noLabel")),
                "rawResolutionRule": normalize_text(question.get("rawResolutionRule")),
                "resolutionRuleNote": normalize_text(question.get("resolutionRuleNote")),
                "missingFields": missing_fields,
            }
        )
    if not unresolved_payload:
        return questions, []

    response_payload = call_llm_completion(completion_config, unresolved_payload)
    updated = [dict(question) for question in questions]
    notes: list[str] = []
    for item in response_payload.get("questions", []):
        if not isinstance(item, dict):
            continue
        raw_index = item.get("index")
        if not isinstance(raw_index, int) or raw_index not in question_index_map:
            continue
        target = updated[question_index_map[raw_index]]
        for field in (
            "title",
            "titleEn",
            "category",
            "deadlineAt",
            "announceAt",
            "scheduledPublishAt",
            "yesLabel",
            "noLabel",
            "rawResolutionRule",
            "resolutionRuleNote",
            "labelReason",
        ):
            current_value = normalize_text(target.get(field))
            incoming_value = normalize_text(item.get(field))
            if not current_value and incoming_value:
                target[field] = incoming_value
        if "needsRuleReview" in item and "needsRuleReview" not in target:
            target["needsRuleReview"] = bool(item.get("needsRuleReview"))
        completion_note = normalize_text(item.get("completionNote"))
        if completion_note:
            notes.append(f"第 {raw_index} 题: {completion_note}")
    return updated, notes


def summarize_missing_rows(questions: list[dict[str, Any]], defaults: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, question in enumerate(questions, start=1):
        missing_fields = build_missing_fields(question, defaults)
        if not missing_fields:
            continue
        rows.append(
            {
                "question_index": index,
                "title": normalize_text(question.get("title")),
                "titleEn": normalize_text(question.get("titleEn")),
                "missing_fields": missing_fields,
            }
        )
    return rows


def normalize_completed_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_payload(payload)


def main() -> int:
    args = parse_args()
    json_file = Path(args.json_file).expanduser().resolve()
    if not json_file.exists():
        print_json({"status": "error", "message": f"未找到 JSON 文件：{json_file}"})
        return 1

    output_json_file = Path(args.output_json_file).expanduser().resolve() if args.output_json_file else json_file
    try:
        payload = load_payload(json_file)
    except ValueError as error:
        print_json({"status": "error", "message": str(error), "json_file": str(json_file)})
        return 1

    raw_defaults = payload.get("defaults")
    defaults = dict(raw_defaults) if isinstance(raw_defaults, dict) else {}
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        print_json({"status": "error", "message": "questions 必须是非空数组", "json_file": str(json_file)})
        return 1

    deterministic_notes: list[str] = []
    completed_questions: list[dict[str, Any]] = []
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            print_json({"status": "error", "message": "questions 中每一项都必须是对象", "json_file": str(json_file)})
            return 1
        completed, notes = apply_deterministic_completion(raw_question, defaults)
        completed_questions.append(completed)
        deterministic_notes.extend(notes)

    llm_config = maybe_get_completion_config()
    try:
        completed_questions, llm_notes = apply_llm_completion(completed_questions, defaults, llm_config)
    except ValueError as error:
        print_json(
            {
                "status": "error",
                "step": "llm_completion",
                "message": str(error),
                "json_file": str(json_file),
            }
        )
        return 1

    completed_payload = dict(payload)
    completed_payload["questions"] = completed_questions
    if defaults:
        completed_payload["defaults"] = defaults

    missing_rows = summarize_missing_rows(completed_questions, defaults)
    if missing_rows and not args.allow_partial:
        attempted_output = output_json_file.with_name(f"{output_json_file.stem}.attempted.json")
        write_payload(attempted_output, completed_payload)
        print_json(
            {
                "status": "error",
                "step": "complete_manual_payload",
                "message": "自动补全后仍有必填字段缺失，不能继续导入。",
                "json_file": str(json_file),
                "attempted_output_json_file": str(attempted_output),
                "llm_configured": llm_config is not None,
                "deterministic_notes": deterministic_notes,
                "llm_notes": llm_notes,
                "missing_rows": missing_rows,
            }
        )
        return 1

    try:
        normalized_payload = normalize_completed_payload(completed_payload)
    except ValueError as error:
        print_json(
            {
                "status": "error",
                "step": "normalize_completed_payload",
                "message": str(error),
                "json_file": str(json_file),
                "llm_configured": llm_config is not None,
                "deterministic_notes": deterministic_notes,
                "llm_notes": llm_notes,
            }
        )
        return 1

    write_payload(output_json_file, normalized_payload)
    print_json(
        {
            "status": "ok",
            "json_file": str(json_file),
            "output_json_file": str(output_json_file),
            "question_count": len(normalized_payload["questions"]),
            "llm_configured": llm_config is not None,
            "deterministic_notes": deterministic_notes,
            "llm_notes": llm_notes,
            "remaining_missing_rows": missing_rows,
            "generated_at": datetime.now(UTC).isoformat(),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
