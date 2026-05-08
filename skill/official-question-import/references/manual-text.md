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

- `title`
- `titleEn`
- `deadlineAt`
- either:
  - `yesLabel` + `noLabel`
  - or at least 2 `options`
- if using `options`, each option must have `label` and `labelEn`

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
3. If the user omits a field that is required for a valid row, ask the smallest possible follow-up.
4. Keep the JSON normalized before writing it into the workbook. Do not write half-structured free text directly.
5. If the user asks to continue adding questions into an existing batch, use append mode instead of replacing the workbook contents.
6. For binary questions, prefer `rawResolutionRule + yesLabel + noLabel` over manually writing long YES/NO option text into `options`.
7. If `yesLabel / noLabel` is present, the normalizer maps them into the first two workbook options automatically.
