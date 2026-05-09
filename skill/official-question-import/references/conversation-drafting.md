# Conversation Drafting

Use this reference when the user does not hand over a ready JSON file and instead gives questions in natural language.

## Target Behavior

The Agent should turn conversation into a valid `manual_text` payload, write it into a batch, run validation, and show a concise preview by default.

## Extraction Order

1. Decide whether the user is creating a new batch or appending to an existing batch.
2. Pull out shared defaults first:
   - `category`
   - `sourceUrl`
   - `announceAt`
   - `scheduledPublishAt`
3. Then normalize each question:
   - `title`
   - `titleEn`
   - `rawResolutionRule`
   - `yesLabel`
   - `noLabel`
   - `deadlineAt`
   - `options`
   - optional row-level overrides
4. Auto-complete missing bilingual title, binary options, category, and time fields whenever possible.
5. Treat all naive datetimes as `America/New_York`.
6. Write the normalized payload to a temporary JSON file.
7. Run `scripts/complete_manual_payload.py` if the payload still has missing fields.
8. Run `scripts/run_conversation_import.py`.
9. If the user wants a custom preview slice, pass `--preview-limit N` or `--preview-all`.

## Minimum Follow-up Rule

Only ask follow-up questions when a row still cannot pass validation after reasonable normalization.

Ask follow-up if any of these is missing:

- both `title` and `titleEn`
- and the Agent still cannot safely infer a valid binary question shape
- or the Agent cannot infer a reasonable time window after applying the default rules

## Shared Defaults Rule

If the user gives one time or category for the whole batch, place it in `defaults` instead of repeating it row by row.

Examples:

- “这 5 道都算金融类” -> `defaults.category`
- “都今晚 8 点发” -> `defaults.scheduledPublishAt`
- “都明天 10 点开奖” -> `defaults.announceAt`
- “来源都是这篇文章” -> `defaults.sourceUrl`

## English Copy Rule

If the user only gives Chinese copy but clearly wants you to draft the batch for preview, you may draft provisional English title and English options for preview.

Before any production submit, explicitly tell the user that English copy was machine-drafted if they did not provide it themselves.

## Binary Label Rule

For binary prediction questions:

- prefer generating `yesLabel / noLabel` from `question_title + rawResolutionRule`
- use `references/binary-label-generator-prompt.md` for generation
- then use `references/binary-label-review-prompt.md` as the review gate
- do not stuff source, exclusions, edge cases, or counting rules into the labels
- put those boundaries into `resolutionRuleNote`
- if the title alone is insufficient and no usable rule text is available, set `needsRuleReview: true`
- if `yesLabel / noLabel` is present, the normalizer will write them back into the first two workbook options automatically

## Time Inference Rule

- Default timezone for generated or interpreted naive datetimes is `America/New_York`
- If the question is sports-match based and the event time can be verified, usually set:
  - `deadlineAt` around 1 hour before start
  - `announceAt` around the expected end time
- If the question is non-sports and no exact public event time is available:
  - `scheduledPublishAt` and `deadlineAt` must be at least 1 day apart
  - `deadlineAt` and `announceAt` must be at least 2 hours apart
  - longer windows are allowed and often preferred
- If the event time cannot be verified and the question obviously depends on a real-world schedule, say so in the preview summary instead of pretending certainty
- `scripts/complete_manual_payload.py` should fail clearly when essential fields remain unresolved; do not continue with guessed placeholders

## Preview Rule

- Default: show concise summary plus planner default preview
- If the user asks “只看前 3 条”, run `scripts/run_conversation_import.py --preview-limit 3` or `scripts/preview_batch_rows.py --limit 3`
- If the user asks “全部给我看”, run `scripts/run_conversation_import.py --preview-all` or `scripts/preview_batch_rows.py --preview-all`
