# Output schema

Repo Brain writes only under `.ai/brain/`.

## Incremental state

- `incremental-state.json`: previous/current indexing state, mode, and reparsed-file count.
- `impact.json`: changed files, impacted files/symbols, and selected test candidates.
- `selected-tests.json`: targeted test files and candidate validation commands.

## Portable layer

- `index.json`: compact counts, languages, graph size, and incremental/full mode.
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

Repo Brain relationships and test selection are static heuristics. They must be verified before high-risk or release-critical changes.
