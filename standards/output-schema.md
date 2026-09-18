# Output schema

Repo Brain writes generated repository context under `.ai/brain/`.

## Incremental state

- `incremental-state.json`: indexed commit, base commit, mode, source-file count and number of files reparsed.
- `impact.json`: changed files, changed source files, reverse-import impact, impacted symbols and selected tests.
- `selected-tests.json`: selected test files plus candidate targeted commands.

## Portable layer

- `index.json`: counts, languages, index mode and high-density symbol files.
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

ast-grep Outline is an optional syntax view. It does not resolve runtime calls or full semantic references. The portable layer remains the fallback.
