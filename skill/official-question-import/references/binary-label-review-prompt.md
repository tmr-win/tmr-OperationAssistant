# Binary Label Review Prompt

Use this exact prompt after generating `yesLabel / noLabel`. It is a review gate, not a drafting prompt.

```text
Review these YES/NO labels for a binary prediction card.

Reject if:
- Either label starts with “Resolves”
- Either label is longer than 52 characters
- YES and NO are not direct complements
- NO includes exclusions that YES does not mirror
- The labels require slow reading to understand the choice
- Data source or edge cases are stuffed into the labels

Return:
{
  "pass": true/false,
  "issue": "",
  "suggested_yes_label": "",
  "suggested_no_label": ""
}
```
