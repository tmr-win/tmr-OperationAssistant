# Binary Option Labels

Use this reference when a binary prediction question needs concise YES/NO labels.

For the exact prompting text, see:

- `references/binary-label-generator-prompt.md`
- `references/binary-label-review-prompt.md`

## Goal

Turn a binary question into short, symmetric labels that describe the two outcomes directly.

The model should compress expression, not invent missing rules.

Best input:

- `question_title`
- `rawResolutionRule`

## Required Output Shape

```json
{
  "yesLabel": "",
  "noLabel": "",
  "resolutionRuleNote": "",
  "needsRuleReview": false,
  "labelReason": ""
}
```

## Generation Rules

1. `yesLabel` describes the proposition becoming true.
2. `noLabel` is the direct logical complement of `yesLabel`.
3. Do not start labels with `Resolves`.
4. Keep each label short: ideally 3-8 words, max 52 characters.
5. Keep YES and NO parallel in grammar, length, and specificity.
6. Keep source, exclusions, counting rules, and edge cases out of labels.
7. Put those boundaries into `resolutionRuleNote`.
8. If the title alone is underspecified and no usable rule text is available, set `needsRuleReview: true`.

## Preferred Templates

### Numeric threshold

- YES: `[metric] > X`
- NO: `[metric] ≤ X`

### Qualifying content appears

- YES: `[qualifying content] appears`
- NO: `No [qualifying content] appears`

## Review Gate

Apply this sequence:

1. Run the generator prompt with:
   - `question_title`
   - `rawResolutionRule`
2. Map its output into:
   - `yesLabel`
   - `noLabel`
   - `resolutionRuleNote`
   - `needsRuleReview`
   - `labelReason`
3. Run the review prompt on the resulting labels.
4. If `pass=false` and suggestions are present, prefer the suggested labels.
5. If the pair still looks weak or the rule text is underspecified, keep `needsRuleReview: true`.
