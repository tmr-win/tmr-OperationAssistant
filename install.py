#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SKILL_NAME = "official-question-import"
SKILL_SOURCE_DIR = REPO_ROOT / "skill" / SKILL_NAME
HOST_TARGET_DIRS = {
    "codex": Path("~/.codex/skills"),
    "claude": Path("~/.claude/skills"),
    "cursor": Path("~/.cursor/skills"),
    "openclaw": Path("~/.openclaw/skills"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="安装或更新 official-question-import Skill 到本机宿主 Skill 目录。"
    )
    parser.add_argument(
        "--target-dir",
        help="Skill 父目录；指定后优先于 --host",
    )
    parser.add_argument(
        "--host",
        choices=sorted(HOST_TARGET_DIRS.keys()),
        help="按宿主默认目录安装，可选 codex / claude / cursor / openclaw",
    )
    parser.add_argument(
        "--link",
        action="store_true",
        help="使用软链接而不是复制文件，适合研发本地联调",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="覆盖安装时不备份旧版本",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出将执行的动作，不真正写入文件",
    )
    return parser.parse_args()


def ensure_source_exists() -> None:
    required = [
        SKILL_SOURCE_DIR / "SKILL.md",
        SKILL_SOURCE_DIR / "agents" / "openai.yaml",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Skill 源目录不完整，缺少文件：{', '.join(missing)}")


def resolve_target_dir(args: argparse.Namespace) -> tuple[Path, str]:
    if args.target_dir:
        return Path(args.target_dir).expanduser().resolve(), "custom"
    if args.host:
        return HOST_TARGET_DIRS[args.host].expanduser().resolve(), args.host
    return HOST_TARGET_DIRS["codex"].expanduser().resolve(), "codex"


def backup_existing(target_skill_dir: Path, backup_root: Path, dry_run: bool) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = backup_root / f"{SKILL_NAME}-{timestamp}"
    if dry_run:
        return backup_dir
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.move(str(target_skill_dir), str(backup_dir))
    return backup_dir


def install_with_copy(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        return
    shutil.copytree(source, target, dirs_exist_ok=False)


def install_with_link(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        return
    target.symlink_to(source, target_is_directory=True)


def main() -> int:
    args = parse_args()
    ensure_source_exists()

    target_dir, resolved_host = resolve_target_dir(args)
    target_skill_dir = target_dir / SKILL_NAME
    backup_root = target_dir / ".backups"

    backup_dir = ""
    replaced_existing = False
    install_mode = "symlink" if args.link else "copy"

    if target_skill_dir.exists() or target_skill_dir.is_symlink():
        replaced_existing = True
        if not args.no_backup:
            backup_dir = str(backup_existing(target_skill_dir, backup_root, args.dry_run))
        elif not args.dry_run:
            if target_skill_dir.is_symlink() or target_skill_dir.is_file():
                target_skill_dir.unlink()
            else:
                shutil.rmtree(target_skill_dir)

    if not args.dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        if target_skill_dir.exists() or target_skill_dir.is_symlink():
            if target_skill_dir.is_symlink() or target_skill_dir.is_file():
                target_skill_dir.unlink()
            else:
                shutil.rmtree(target_skill_dir)

    if args.link:
        install_with_link(SKILL_SOURCE_DIR, target_skill_dir, args.dry_run)
    else:
        install_with_copy(SKILL_SOURCE_DIR, target_skill_dir, args.dry_run)

    payload = {
        "status": "ok",
        "mode": install_mode,
        "dry_run": args.dry_run,
        "host": resolved_host,
        "source": str(SKILL_SOURCE_DIR),
        "target_dir": str(target_dir),
        "target_skill_dir": str(target_skill_dir),
        "replaced_existing": replaced_existing,
        "backup_dir": backup_dir,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
