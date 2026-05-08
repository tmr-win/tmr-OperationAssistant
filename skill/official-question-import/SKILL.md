---
name: official-question-import
description: Use this skill when研发、运营支持或会用 Codex 的运营需要初始化官方题导题工作目录、创建导题批次、把对话里的题目整理后写入 questions.xlsx、批量改写现有批次文案、校验 Excel/CSV、预览导题计划、检查图片和表格是否匹配，或将批次提交到测试/生产环境。 This skill supports explicit batch names and fuzzy requests like “最新一批”“今天那批”“市场热点那批”, and it can rewrite an existing batch in a more口语化 / personal style before re-validating it. It defaults to initializing the tool under ~/Desktop/ops-import-tool but allows custom directories. Production submit must never run immediately: always summarize the target batch first and wait for an explicit confirmation such as “确认提交”.
---

# Official Question Import

Use this skill to run the official-question import workflow on top of a reusable local workspace. The skill does not assume the workspace already exists; it can initialize one on first use after confirmation.

## Core Rules

1. Default workspace: `~/Desktop/ops-import-tool`.
2. If the user provides a custom directory, prefer it over the default.
3. If no workspace exists yet, do not initialize silently. First explain what will be created, then wait for a clear confirmation before running initialization.
4. For `new / validate / plan / check`, execute directly once the target workspace/batch is clear.
5. For `submit`, always do this order:
   1. Resolve the batch.
   2. Run `validate`.
   3. Run `plan`.
   4. Summarize the batch, environment, counts, and risks.
   5. Wait for an explicit confirmation like “确认提交”.
   6. Only then run `submit`.
6. When the user uses fuzzy language like “最新一批”“今天那批”“市场热点那批”, resolve candidates with `scripts/resolve_batch.py`. If there are multiple plausible matches, ask a short follow-up instead of guessing.
7. Default preview behavior is concise: show summary plus the bundled planner's default preview rows. In the current implementation, that means the first 10 rows. If the user asks for more detail than the default planner exposes, explain the current limit honestly and then inspect the batch files directly if needed.
8. If the user explicitly asks to see only the first few rows or to see all rows, run `scripts/preview_batch_rows.py` or pass `--preview-limit / --preview-all` to `scripts/run_conversation_import.py`.
9. When the user gives questions directly in conversation, first extract them into structured JSON, then run `scripts/run_conversation_import.py` so the flow can normalize payload, write workbook, validate, and plan in one pass.
10. If direct conversational drafting is missing essential fields, ask the smallest possible follow-up. The minimum fields are described in `references/manual-text.md`.
11. When the user only gives Chinese copy and clearly wants a preview batch quickly, you may draft provisional English copy for preview. Before any production submit, explicitly tell the user that the English copy was machine-drafted if they did not provide it.
12. Submit prefers a locally saved ops-admin login state. If login is missing or expired, run `scripts/ensure_login.py`, ask the user for ops-admin email and password, let the script exchange them for a token, save only the resulting token locally, and then continue. If the user does not want to provide a password, fall back to pasted Bearer token mode.
13. Treat the admin page URL and the `identity-service` URL as separate endpoints. Default to `https://admin.tmr.win/admin/questions/list` for the admin page and `https://tmr.win/identity-service` for auth APIs.
14. When the user asks to “改口语一点”“像我自己写的”“改现有这批题”, do not ask them to rewrite each row manually. Export the current batch JSON, rewrite it in memory, preview a diff, and only then write it back.

## Workspace Flow

### First-time initialization

Use:

```bash
python3 scripts/init_workspace.py
python3 scripts/init_workspace.py --target "~/Desktop/ops-import-tool"
python3 scripts/init_workspace.py --target "/custom/path/ops-import-tool"
```

Before calling it for the first time, tell the user:

- the target directory
- that the tool workspace will contain `模板区`、`导题批次`、`报告区`
- that a template and helper runtime will be prepared

### Create a batch

Use:

```bash
python3 scripts/create_batch.py --workspace "~/Desktop/ops-import-tool" --topic "market-hot"
python3 scripts/create_batch.py --workspace "~/Desktop/ops-import-tool" --name "2026-04-28-market-hot-01"
```

If the user says “新建今天的导题批次” without a name, prefer `--topic` and let the script generate the dated batch name.

### Resolve a batch

Use:

```bash
python3 scripts/resolve_batch.py --workspace "~/Desktop/ops-import-tool" --query "最新一批"
python3 scripts/resolve_batch.py --workspace "~/Desktop/ops-import-tool" --query "市场热点"
```

The script returns structured JSON. If it returns `ambiguous`, ask the user to choose a candidate.

### Export / Diff for rewrite

Use:

```bash
python3 scripts/export_batch_to_json.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --output-json-file "/tmp/current-batch.json"
python3 scripts/preview_batch_diff.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --json-file "/tmp/rewritten-batch.json"
python3 scripts/preview_batch_diff.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --json-file "/tmp/rewritten-batch.json" --preview-all
```

Behavior:

- `export_batch_to_json.py` exports the current batch workbook into the same JSON shape used by `manual_text`
- the Agent should edit that JSON directly according to the user's rewrite intent
- `preview_batch_diff.py` shows which rows and fields changed before any workbook write
- after the user confirms the diff, apply the rewritten JSON with `scripts/run_conversation_import.py --query ... --mode replace`

### Validate / Plan / Submit

Use:

```bash
python3 scripts/run_batch_action.py validate --workspace "~/Desktop/ops-import-tool" --query "最新一批"
python3 scripts/run_batch_action.py plan --workspace "~/Desktop/ops-import-tool" --query "2026-04-28-market-hot-01"
python3 scripts/run_batch_action.py submit --workspace "~/Desktop/ops-import-tool" --query "今天那批" --confirmed
python3 scripts/run_batch_action.py submit --workspace "~/Desktop/ops-import-tool" --query "今天那批" --confirmed --email "<邮箱>" --password "<密码>"
python3 scripts/run_batch_action.py submit --workspace "~/Desktop/ops-import-tool" --query "今天那批" --confirmed --token "<TOKEN>"
```

`submit` is protected by `--confirmed`. Do not pass it until the user has explicitly confirmed. The wrapper first checks the local saved login state; if no usable session exists, it returns a structured `credentials_required` result.

### Ensure Login / Logout

Use:

```bash
python3 scripts/ensure_login.py
python3 scripts/ensure_login.py --email "<邮箱>" --password "<密码>"
python3 scripts/ensure_login.py --token "<TOKEN>"
python3 scripts/ensure_login.py --force-rebind
python3 scripts/logout.py
```

Behavior:

- `ensure_login.py` returns `authenticated` when the local ops-admin login state is usable
- if it returns `credentials_required`, first ask the user for ops-admin email and password
- after the user sends credentials, run `python3 scripts/ensure_login.py --email "<邮箱>" --password "<密码>"`, then rerun the original submit action
- if the user does not want to share a password, fall back to `python3 scripts/ensure_login.py --token "<TOKEN>"`
- `logout.py` clears the local saved token and revokes the current runtime session when possible

### Login collection

When the user needs to log in, guide them with this exact flow:

1. First ask them to send the ops-admin email and password directly in chat.
2. Explain that the skill will not save the plain-text password, only the resulting token.
3. If they refuse to share the password, ask them to log in to `https://admin.tmr.win/admin/questions/list` in the browser.
4. Then ask them to open Developer Tools, switch to `Network`, refresh the page, and copy the `Authorization` request header value.
5. Accept either `Bearer <TOKEN>` or just `<TOKEN>`.

### Write questions from conversation

Use:

```bash
python3 scripts/run_conversation_import.py --workspace "~/Desktop/ops-import-tool" --topic "market-hot" --json-file "/tmp/manual-questions.json"
python3 scripts/run_conversation_import.py --workspace "~/Desktop/ops-import-tool" --batch-name "2026-04-28-market-hot-01" --json-file "/tmp/manual-questions.json" --mode append
python3 scripts/run_conversation_import.py --workspace "~/Desktop/ops-import-tool" --query "最新一批" --json-file "/tmp/manual-questions.json"
python3 scripts/run_conversation_import.py --workspace "~/Desktop/ops-import-tool" --topic "market-hot" --json-file "/tmp/manual-questions.json" --preview-limit 3
python3 scripts/run_conversation_import.py --workspace "~/Desktop/ops-import-tool" --query "最新一批" --json-file "/tmp/manual-questions.json" --preview-all
```

Behavior:

- `run_conversation_import.py` first normalizes and validates the JSON payload, then calls ingest, validate, and plan
- `--query` writes into an existing resolved batch
- `--batch-name` writes into the named batch and creates it first if needed
- `--topic` creates a new dated batch automatically
- if none of `--query / --batch-name / --topic` is provided, create a new batch with topic `manual-text`
- `--mode replace` is the safe default for a fresh direct-drafting batch because it clears the template example row
- `--mode append` is for adding more questions into an existing batch
- if the Agent needs only payload normalization, use `scripts/validate_manual_payload.py`
- if the Agent needs workbook row preview after import, use `scripts/preview_batch_rows.py`

## Suggested Interaction Pattern

### Direct execution requests

Examples:

- “帮我新建今天的官方题导题批次”
- “帮我校验最新一批”
- “帮我预览市场热点那批”
- “帮我检查这批题的图片有没有对上”

These can run immediately once the workspace and batch are resolved.

### Production submit requests

Example:

- “帮我把今天这批题提交到生产”

Do not submit immediately. First summarize:

- workspace path
- resolved batch name
- title count
- image count
- whether validation passed
- plan summary
- environment / base URL
- whether the batch appears to update existing items

Then wait for a clear confirmation.

### Direct conversational drafting

When the user says things like:

- “我直接给你题，你帮我整理后导进去”
- “把今天这批市场热点题建好并预览一下”
- “我给你 5 道题，你先别提交，先让我看计划”

Do this order:

1. Normalize the request into the JSON shape defined in `references/manual-text.md`.
2. Use `references/conversation-drafting.md` to decide shared defaults, follow-up threshold, and preview behavior.
3. If key fields are missing, ask only the minimum follow-up needed to make the rows valid.
4. Write the payload to a temporary JSON file.
5. Run `scripts/run_conversation_import.py`.
6. Show a concise summary by default.
7. Only run `submit` after an explicit confirmation for the target environment.

### Existing batch rewrite

When the user says things like:

- “把今天这批题都改口语一点”
- “这批标题太官方了，像我自己写的那种”
- “第 3 题和第 5 题重写一下”
- “英文也顺一下，别太像机翻”

Do this order:

1. Resolve the target batch.
2. Run `scripts/export_batch_to_json.py`.
3. Rewrite the exported JSON in memory based on the user's instruction.
4. Run `scripts/preview_batch_diff.py`.
5. Summarize the changed rows and changed fields.
6. Wait for explicit confirmation before writing back.
7. Apply the rewritten JSON with `scripts/run_conversation_import.py --query ... --mode replace`.
8. Return the refreshed validate / plan result.

## Current Scope

Implemented now:

- workspace initialization
- batch creation
- fuzzy batch resolution
- `manual_text` conversational drafting into `questions.xlsx`
- payload normalization and validation for direct conversational drafting
- validate / plan / submit wrappers around the existing import script

Reserved for later:

- `crawler_candidate` source integration
- mixed-source import flows

## References

- `references/workflow.md`: end-to-end workflow, defaults, and expected user experience
- `references/manual-text.md`: structured JSON shape and minimum fields for direct conversational drafting
- `references/conversation-drafting.md`: extraction heuristics, follow-up rules, and preview policy for natural-language drafting
- `references/confirmation-rules.md`: what must be confirmed before write actions
- `references/batch-rewrite.md`: export / diff / rewrite workflow for modifying an existing batch
- `references/crawler-extension.md`: reserved extension design for future crawler integration
