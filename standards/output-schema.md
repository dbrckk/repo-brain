# Output schema

Repo Brain writes only under `.ai/brain/`.

## Portable layer

- `index.json`: compact counts, languages, and high-density symbol files.
- `lookup.json`: portable symbol-to-file lookup.
- `symbols.json`: portable symbol metadata.
- `imports.json`: imports grouped by source file.
- `code-graph.json`: lightweight inferred internal import edges.
- `summary.md`: smallest human/agent-readable entrypoint.

## ast-grep enrichment

- `capabilities.json`: declares whether ast-grep Outline succeeded.
- `ast-routing.json`: explains shard routing.
- `ast-symbols/<initial>.json`: exact symbol/member ranges, sharded by lowercase first character.
- `file-outlines/<root>.json`: compact AST structure grouped by first path component.

ast-grep Outline is an optional syntax view. It does not resolve types, references, runtime calls, or imports. The portable layer remains the fallback.
