# Repo Brain agent instructions

## Shared policy — 88 validated development rules

- Official [88-rule catalog](https://github.com/dbrckk/repo-standards/blob/db2f86657ada74a0561e07189f9942d6b66ebb4a/standards/88-rules.md), [agent skill](https://github.com/dbrckk/repo-standards/blob/db2f86657ada74a0561e07189f9942d6b66ebb4a/skills/repo-excellence-88/SKILL.md) and [educational wiki](https://github.com/dbrckk/repo-standards/blob/db2f86657ada74a0561e07189f9942d6b66ebb4a/docs/WIKI-88.md).
- Apply relevant foundational rules; activate conditional rules only when applicable to this repository.
- **Do not create new unit tests.** Keep existing tests intact; prefer functional/integration validation, lint, build, and real smoke checks as appropriate. Report what actually ran.
- Inspect the current branch, changes, code, README and project-specific instructions before editing. Prefer the smallest complete and reversible change.
- Update project-state documentation and educational notes when warranted; capture proven reusable methods as skills.
- Priority: reliability > real functionality > security > architecture > performance > interface > secondary features.
- This is a **policy-only adoption**: no CI workflow, test suite, or runtime configuration is changed. Do not override local architecture or higher-priority instructions.

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
