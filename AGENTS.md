# Repo Brain agent instructions

- Keep generated indexes deterministic and compact.
- Prefer symbol/file relationships over copied source code.
- Never include secret values in generated context.
- Do not parse vendor, generated, cache, build, binary or asset directories.
- Preserve line numbers when extracting symbols.
- Treat inferred relationships as hints, not proof of runtime behavior.
- Keep the output useful to agents reading only a few kilobytes first.
