# Future Crawler Extension

This skill should reserve a source-type abstraction even though crawler integration is not implemented yet.

## Current source types

- `manual_file`
- `manual_text` (reserved, not implemented in Phase 1)

## Reserved source types

- `crawler_candidate`
- `mixed`

## Why reserve it now

Future crawler integration will likely change:

- field completeness assumptions
- candidate question adoption flow
- image source behavior
- submit confirmation wording

The interaction model should therefore remain source-agnostic:

1. Identify source type
2. Normalize to a batch
3. Validate / plan
4. Confirm before submit
