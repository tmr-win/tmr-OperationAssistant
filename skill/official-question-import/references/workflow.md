# Workflow

## Current Workflow

Current implemented workflow:

1. Initialize or locate a workspace
2. Create or resolve a batch
3. If the user gives questions in conversation, normalize them into JSON and run `scripts/run_conversation_import.py`
4. Review the validation result
5. Review the plan output
6. Confirm before submit
7. Submit and inspect the report

## Default Workspace

- Default: `~/Desktop/ops-import-tool`
- Users may override with a custom path
- The skill should remember the last initialized workspace and prefer it later

## Default Submit Target

- Default admin page URL: `https://admin.tmr.win/admin/questions/list`
- Default identity-service URL: `https://tmr.win/identity-service`
- Default login flow: the skill first asks for ops-admin email and password, exchanges them for a token, and saves only the resulting token locally
- Token paste from the already logged-in admin page remains available as a fallback when the user does not want to share a password
- The submit wrapper may still override URL or pass an explicit token when the user explicitly asks for another environment
- URL normalization must accept admin page URLs such as `/admin/questions/list` and convert them to the gateway root automatically for submit traffic only
- Auth traffic must use the explicit `identity-service` URL and must not assume it shares the same host as the admin page
- Local auth state is stored outside the repository and reused across submit actions until it expires or is cleared

## Batch Naming

- Preferred pattern: `YYYY-MM-DD-topic-01`
- If only a topic is provided, the helper script generates the next dated batch name automatically

## Preview Policy

- Default: summary plus the planner's built-in first 10 items
- If the user asks for more than the default preview, handle it as an explicit detailed-inspection request
- Full-list preview is a future enhancement rather than a current guaranteed script capability

## Manual Text Drafting

- Direct conversational drafting is now implemented through `scripts/run_conversation_import.py`
- The write path is `conversation -> structured JSON -> payload normalize -> questions.xlsx -> validate -> plan -> submit`
- Custom row preview is implemented through `scripts/preview_batch_rows.py`
- The current skill still uses the existing import engine; it does not bypass validation or submit logic
