# Repo Brain agent instructions

- Prefer incremental portable and AST reparsing when prior state is valid.
- Fall back to full rebuild when history/state cannot be trusted.
- Read impact and selected-tests before broad exploration.
- Use AST shards for exact ranges.
- Use references/dependencies only as static routing hints.
- Verify authoritative source before edits.
- Never include secrets in generated context.
- Keep generated indexes deterministic and compact.
