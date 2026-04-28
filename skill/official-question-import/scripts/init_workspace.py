#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from common import (
    DEFAULT_WORKSPACE,
    TEMPLATE_DIR_NAME,
    TEMPLATE_FILE_NAME,
    TOOL_TEMPLATE_DIR,
    print_json,
    resolve_workspace,
    write_last_workspace,
)


def main() -> int:
    target_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    workspace = resolve_workspace(target_arg or None, require_exists=False) or DEFAULT_WORKSPACE
    workspace.mkdir(parents=True, exist_ok=True)

    shutil.copytree(TOOL_TEMPLATE_DIR, workspace, dirs_exist_ok=True)

    npm_install = subprocess.run(
        ["npm", "install"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if npm_install.returncode != 0:
        print_json(
            {
                "status": "error",
                "step": "npm_install",
                "workspace": str(workspace),
                "stdout": npm_install.stdout,
                "stderr": npm_install.stderr,
            }
        )
        return npm_install.returncode

    template_path = workspace / TEMPLATE_DIR_NAME / TEMPLATE_FILE_NAME
    template_result = subprocess.run(
        [
            "npm",
            "run",
            "import:official-questions",
            "--",
            "template",
            str(template_path),
        ],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if template_result.returncode != 0:
        print_json(
            {
                "status": "error",
                "step": "generate_template",
                "workspace": str(workspace),
                "stdout": template_result.stdout,
                "stderr": template_result.stderr,
            }
        )
        return template_result.returncode

    write_last_workspace(workspace)
    print_json(
        {
            "status": "ok",
            "workspace": str(workspace),
            "template": str(template_path),
            "stdout": template_result.stdout.strip(),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
