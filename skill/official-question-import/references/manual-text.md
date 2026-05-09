# Manual Text

Use this reference when the user gives official questions directly in conversation and wants the Agent to draft the batch for them.

## JSON Shape

```json
{
  "defaults": {
    "category": "金融",
    "sourceUrl": "https://example.com/source",
    "announceAt": "2026-05-01 10:00",
    "scheduledPublishAt": "2026-04-28 10:00"
  },
  "questions": [
    {
      "title": "比特币本月收盘价是否高于10万美元？",
      "titleEn": "Will Bitcoin close above $100,000 this month?",
      "rawResolutionRule": "以官方收盘价来源为准，按截止日最后一个有效收盘价判断。",
      "yesLabel": "Close > $100,000",
      "noLabel": "Close ≤ $100,000",
      "resolutionRuleNote": "Use the official closing-price source and final valid close before deadline.",
      "needsRuleReview": false,
      "labelReason": "Numeric threshold, direct complement pair.",
      "category": "金融",
      "sourceUrl": "https://example.com/questions/btc-close-above-100k",
      "deadlineAt": "2026-04-30 16:00",
      "announceAt": "2026-05-01 10:00",
      "scheduledPublishAt": "2026-04-28 10:00",
      "candidateQuestionId": "",
      "imageFileName": "btc-close-above-100k.png",
      "options": [
        {
          "label": "Close > $100,000",
          "labelEn": "Close > $100,000"
        },
        {
          "label": "Close ≤ $100,000",
          "labelEn": "Close ≤ $100,000"
        }
      ]
    }
  ]
}
```

## Minimum Required Fields

Each question must have:

- at least one of:
  - `title`
  - `titleEn`

The remaining fields may be auto-completed by the Agent workflow before workbook write, including:

- the missing bilingual title
- `category`
- `deadlineAt`
- `announceAt`
- `scheduledPublishAt`
- either:
  - `yesLabel` + `noLabel`
  - or at least 2 `options`

If using `options`, each option must have `label` and `labelEn`.

## Optional Fields

- Batch-level defaults: `category`, `sourceUrl`, `announceAt`, `scheduledPublishAt`
- Row-level overrides: same keys can also be set on each question
- `candidateQuestionId`
- `imageFileName`
- `rawResolutionRule`
- `resolutionRuleNote`
- `needsRuleReview`
- `labelReason`

## Direct Drafting Rules

1. If the user gives multiple questions with shared attributes, prefer filling them into `defaults`.
2. If the user omits a field that can safely inherit from `defaults`, do not ask again.
3. If the user only gives a Chinese or English stem, auto-complete the missing bilingual title, category, binary options, and time fields before asking follow-up questions.
4. All naive datetimes must be interpreted in `America/New_York`.
5. If the question is sports-match based and the event time can be verified, usually set:
   - `deadlineAt` around 1 hour before start
   - `announceAt` around the expected end time
6. If the question is non-sports and no exact public event time is available:
   - `scheduledPublishAt` and `deadlineAt` must be at least 1 day apart
   - `deadlineAt` and `announceAt` must be at least 2 hours apart
   - longer windows are allowed and often preferred
7. `scheduledPublishAt` should be treated as a suggested publish time for preview and planning. By default, production submit should not use it to auto-publish.
8. If the user omits a field that is still required after reasonable auto-completion, ask the smallest possible follow-up.
9. Keep the JSON normalized before writing it into the workbook. Do not write half-structured free text directly.
10. If the user asks to continue adding questions into an existing batch, use append mode instead of replacing the workbook contents.
11. For binary questions, prefer `rawResolutionRule + yesLabel + noLabel` over manually writing long YES/NO option text into `options`.
12. If `yesLabel / noLabel` is present, the normalizer maps them into the first two workbook options automatically.
13. `scripts/complete_manual_payload.py` is the executable completion stage. It should try deterministic completion first, then optional structured LLM completion if credentials are configured, and fail clearly if essential fields remain unresolved.
