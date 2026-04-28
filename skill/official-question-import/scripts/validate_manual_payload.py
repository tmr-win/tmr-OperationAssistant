#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import print_json
from manual_payload import load_payload, normalize_payload, write_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-file", required=True)
    parser.add_argument("--output-json-file")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    json_file = Path(args.json_file).expanduser().resolve()
    if not json_file.exists():
        print_json({"status": "error", "message": f"未找到 JSON 文件：{json_file}"})
        return 1

    try:
        payload = load_payload(json_file)
        normalized_payload = normalize_payload(payload)
    except ValueError as error:
        print_json({"status": "error", "message": str(error), "json_file": str(json_file)})
        return 1

    output_file = Path(args.output_json_file).expanduser().resolve() if args.output_json_file else json_file
    write_payload(output_file, normalized_payload)
    print_json(
        {
            "status": "ok",
            "json_file": str(json_file),
            "output_json_file": str(output_file),
            "question_count": len(normalized_payload["questions"]),
            "defaults_keys": sorted(normalized_payload.get("defaults", {}).keys()),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
