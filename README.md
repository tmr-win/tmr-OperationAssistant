# tmr-OperationAssistant

`tmr-OperationAssistant` 是运营辅助 Skill 仓库。当前主能力是 `official-question-import`，用于让研发和运营通过 Agent 更快完成官方题导入、预览、校验与提交。

当前仓库分成两层：

- `official-question-import`：真正执行导题、预览、校验、提交和本地登录态鉴权的 runtime skill
- `official-question-import-bootstrap-skill`：安装、刷新并 handoff 到 runtime skill 的 bootstrap skill

仓库已经预留后续扩展空间，未来如需接入爬虫相关能力，可以继续在这个仓库内追加新的 runtime skill 或 references，而不需要另起一套发布方式。

## 仓库地址

正式仓库地址：

```text
git@github.com:tmr-win/tmr-OperationAssistant.git
```

## 仓库结构

- `skill/official-question-import/`：runtime skill 内容
- `bootstrap/official-question-import-bootstrap-skill/`：bootstrap skill 内容
- `install.py`：本地安装脚本，适合研发调试或 fallback
- `install.sh`：shell 包装脚本

## 推荐安装方式

优先使用宿主自己的 Skill 导入、同步或学习流程，直接指向这个仓库。

bootstrap skill 文件在：

```text
bootstrap/official-question-import-bootstrap-skill/SKILL.md
```

它负责：

- 识别宿主
- 定位 runtime skill 源码
- 安装或刷新 `official-question-import`
- 校验 `scripts/ensure_login.py`、`scripts/run_batch_action.py` 等关键文件
- handoff 到 runtime skill

安装完成后，可以让 Agent 直接执行：

```text
Use official-question-import to initialize a workspace, prepare batches, and handle first-run ops-admin login setup before submit.
```

## 命令行安装 Fallback

如果某个宿主没有现成的 Skill 导入能力，可以直接使用仓库里的安装脚本。

```bash
git clone git@github.com:tmr-win/tmr-OperationAssistant.git
cd tmr-OperationAssistant
python3 install.py --host codex
```

或：

```bash
git clone git@github.com:tmr-win/tmr-OperationAssistant.git
cd tmr-OperationAssistant
bash install.sh --host codex
```

支持宿主：

- `codex`
- `claude`
- `cursor`
- `openclaw`

如果本机已经装过旧版本，脚本会先备份到目标 Skill 目录下的 `.backups/`。

## 常用参数

```bash
python3 install.py --host codex
python3 install.py --host claude
python3 install.py --target-dir ~/.codex/skills
python3 install.py --link
python3 install.py --no-backup
python3 install.py --dry-run
```

说明：

- `--host`：按宿主默认路径安装
- `--target-dir`：手动指定 Skill 父目录；指定后优先于 `--host`
- `--link`：用软链接安装，适合研发本地联调
- `--no-backup`：覆盖时不保留旧版本
- `--dry-run`：只看将执行什么，不真正写入

## 安装完成后怎么用

安装成功后，Skill 会出现在对应宿主的 Skill 目录，例如：

- Codex：`~/.codex/skills/official-question-import`
- Claude：`~/.claude/skills/official-question-import`
- Cursor：`~/.cursor/skills/official-question-import`
- openclaw：`~/.openclaw/skills/official-question-import`

Agent 后续可以通过这些方式触发：

- 显式：`使用 $official-question-import`
- 隐式：说“帮我导官方题”“帮我预览最新一批”“把这几道题整理成导题批次”

## 登录授权说明

runtime skill 不在仓库里内置账号密码，也不会保存明文密码。

当用户第一次执行 `submit`，或本地登录态失效时，skill 会：

1. 提示用户直接提供运营后台邮箱和密码
2. skill 调登录接口换取 access token
3. skill 只保存登录后的 token / refresh 能力，不保存明文密码
4. 后续自动复用本地登录态，过期时优先自动 refresh
5. 如果用户不想提供密码，也可以退回手动粘贴 Bearer token 的兜底流程
