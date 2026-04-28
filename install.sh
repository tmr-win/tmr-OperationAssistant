#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="${OFFICIAL_QUESTION_IMPORT_SKILL_REPO:-git@github.com:tmr-win/tmr-OperationAssistant.git}"

if [[ -f "$SCRIPT_DIR/install.py" && -d "$SCRIPT_DIR/skill/official-question-import" ]]; then
  exec python3 "$SCRIPT_DIR/install.py" "$@"
fi

if [[ -z "$REPO_URL" ]]; then
  echo "未找到本地仓库文件。"
  echo "如果你是通过远程脚本执行，请先设置 OFFICIAL_QUESTION_IMPORT_SKILL_REPO=<git 仓库地址>。"
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

git clone --depth 1 "$REPO_URL" "$TMP_DIR/repo" >/dev/null 2>&1
exec python3 "$TMP_DIR/repo/install.py" "$@"
