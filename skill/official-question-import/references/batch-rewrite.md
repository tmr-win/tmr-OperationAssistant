# Batch Rewrite

Use this reference when the user wants to modify an existing batch instead of drafting a new one from scratch.

## Target Behavior

The Agent should treat the current batch as editable source material:

1. Resolve the target batch.
2. Export the current workbook into the same structured JSON shape used by `manual_text`.
3. Apply the user's rewrite intent to that JSON.
4. Preview a diff before writing.
5. After confirmation, write the updated JSON back into the batch workbook.
6. Run `validate` and `plan` again automatically.

## Supported V1 Rewrite Intent

V1 focuses on batch editing for copy and obvious field fixes:

- overall tone changes such as “更口语一点”“像个人写的”“少一点官方腔”
- partial title / titleEn rewrites
- option text / option English rewrites
- single-row field fixes such as deadline / source / category
- whole-batch shared default updates

V1 does not try to infer complex row reordering or merge unrelated batches.

## Recommended Command Sequence

### 1. Export current batch

```bash
python3 scripts/export_batch_to_json.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --output-json-file "/tmp/current-batch.json"
```

### 2. Rewrite JSON in memory

The Agent should edit the exported JSON itself according to the user's intent.

Rules:

- preserve row order unless the user explicitly asks to reorder
- preserve untouched fields
- if only style is requested, do not silently modify deadlines or source URLs
- if English copy is regenerated, mention that in the preview summary

### 3. Preview diff

```bash
python3 scripts/preview_batch_diff.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --json-file "/tmp/rewritten-batch.json"
python3 scripts/preview_batch_diff.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --json-file "/tmp/rewritten-batch.json" --preview-all
```

### 4. Apply rewrite after confirmation

```bash
python3 scripts/run_conversation_import.py --workspace "~/Desktop/ops-import-tool" --query "今天那批" --json-file "/tmp/rewritten-batch.json" --mode replace
```

This write path already re-runs:

- payload normalization
- workbook write
- validate
- plan

## Preview Expectations

The diff preview should emphasize:

- which rows changed
- which fields changed
- title before / after
- whether defaults changed
- whether rows were added or removed

## Confirmation Rule

Do not write the rewritten JSON back into the workbook until the user explicitly confirms the diff result.
