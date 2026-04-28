---
name: official-question-import-bootstrap-skill
description: Bootstrap manual for installing or refreshing `official-question-import` for the current agent host. Use this file to detect the host, install or sync the runtime Skill from the team repository or current workspace source into the correct host directory, verify required files, and then hand off into `official-question-import`.
---

# official-question-import Bootstrap Skill

## Purpose

Use this file only for installation, refresh, and handoff of `official-question-import`.

Your job here is to:

- 识别当前宿主
- 定位 `official-question-import` 的运行时源码
- 安装或刷新到正确的宿主 Skill 目录
- 校验运行时文件完整
- 切换到 `official-question-import`

运行时登录授权、导题、预览、提交都属于 `official-question-import` 本体，不属于 bootstrap。

## Source Priority

按下面顺序选择源码：

1. 如果用户明确给了团队仓库地址，优先使用该仓库。
2. 否则，默认正式源码仓库是：

```text
git@github.com:tmr-win/tmr-OperationAssistant.git
```

3. 如果当前工作区就是该仓库 checkout，优先使用当前工作区内的：

```text
./skill/official-question-import
```

4. 如果 bootstrap 文件已经位于该仓库 checkout 内，也可以使用与其同仓库的 sibling runtime 目录。
5. 如果以上都没有，标记为 `blocked`，并要求用户提供正式仓库地址或当前 checkout 路径。

## State Machine

- `blocked`: 宿主不明确、源码不存在，或目标路径无法安全确定
- `install_required`: 目标 Skill 目录不存在
- `refresh_required`: 目标目录存在但缺文件、过旧，或用户明确要求刷新
- `runtime_ready`: runtime skill 已安装完成，可以 handoff

## Host Mapping

支持宿主：

- `codex`
- `claude`
- `cursor`
- `openclaw`

目标路径：

| Host | Runtime Skill target | Parent directory check |
| --- | --- | --- |
| `codex` | `./.codex/skills/official-question-import` | `test -d ./.codex` |
| `claude` | `./.claude/skills/official-question-import` | `test -d ./.claude` |
| `cursor` | `./.cursor/skills/official-question-import` | `test -d ./.cursor` |
| `openclaw` | `~/.openclaw/skills/official-question-import` | `test -d ~/.openclaw` |

宿主识别规则沿用 `tmrwin-bootstrap-skill` 的思路：

1. 用户或环境已明确给出宿主时，直接采用
2. 本地存在单一宿主标记目录时，使用该宿主
3. 如果信号冲突或无法判断，标记 `blocked`

## Install Procedure

1. 解析宿主
2. 优先解析当前 checkout 是否已包含 `skill/official-question-import`
3. 如果当前工作区没有 runtime 源码，再回退到正式仓库地址
4. 校验宿主父目录存在
5. 将 runtime skill 安装或同步到目标目录
6. 校验至少存在：

```bash
test -f <target>/SKILL.md
test -f <target>/scripts/run_batch_action.py
test -f <target>/scripts/ensure_login.py
test -f <target>/scripts/logout.py
test -d <target>/references
```

7. 如果宿主需要刷新 Skill 列表，则执行宿主自己的刷新动作
8. handoff 到 `official-question-import`

## Handoff

当 `runtime_ready` 后，继续使用：

```text
Use official-question-import to initialize the workspace, prepare batches, and handle first-run ops-admin browser authorization before submit.
```

如果用户没有给出更细的任务，默认 handoff 目标是：

- 初始化或定位导题工作目录
- 当第一次 `submit` 需要授权时，走浏览器登录授权流程

## Guidance

- bootstrap 只负责安装、刷新、handoff
- 不要在 bootstrap 中要求用户输入账号密码
- token 获取与本地保存必须交给 runtime skill
- 使用宿主标准 Skill 目录，不要发 zip，不要临时拷贝到杂散目录
- 当正式仓库和本地 checkout 同时存在时，优先使用当前 checkout，避免把旧临时目录当成 canonical source
