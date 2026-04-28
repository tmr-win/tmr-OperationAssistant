# Confirmation Rules

## Direct Execution

These actions may run immediately once the workspace and batch are clear:

- initialize workspace, after one-time setup confirmation
- create batch
- validate batch
- plan batch
- inspect report
- check image/file alignment

## Mandatory Confirmation

These actions must not run immediately:

- submit to production
- any future write action that modifies online official questions in bulk

Before submit, summarize:

- workspace path
- batch name
- title count
- image count
- validation result
- plan result
- target environment
- any obvious overwrite/update signals

Then wait for a clear confirmation phrase like:

- 确认提交
- 可以提交
- 执行提交
