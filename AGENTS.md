# Repo Brain agent instructions

- Read `.ai/session-state.json` first when it exists.
- Prefer `.ai/brain/task-route.json` and bounded context packets over broad repository exploration.
- Default to a small task context; expand only when evidence shows it is insufficient.
- Prefer incremental portable and AST reparsing when prior state is valid.
- Reuse hash-cache entries for unchanged files instead of reparsing or resummarizing them.
- Fall back to full rebuild when history/state cannot be trusted.
- Read impact and selected-tests before broad exploration.
- Use AST shards for exact ranges.
- Use references/dependencies only as static routing hints.
- Verify authoritative source before edits.
- Checkpoint the active task, touched files, tests and next action before ending substantial work.
- Never include secrets in generated context.
- Keep generated indexes deterministic and compact.
