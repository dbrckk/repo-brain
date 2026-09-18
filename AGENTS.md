# Repo Brain agent instructions

- Keep generated indexes deterministic and compact.
- Prefer incremental reparsing over full rebuilds when the previous state is valid.
- Fall back to a full rebuild when repository history or previous state cannot be trusted.
- Prefer symbol/file relationships over copied source code.
- Never include secret values in generated context.
- Do not parse vendor, generated, cache, build, binary or asset directories.
- Preserve line numbers when extracting symbols.
- Treat inferred relationships and selected tests as hints, not proof of runtime behavior or complete coverage.
- Verify targeted test commands against the repository's canonical tooling before execution when confidence is not high.
- Keep the output useful to agents reading only a few kilobytes first.
