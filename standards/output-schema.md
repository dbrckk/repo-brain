# Output schema

Repo Brain writes under `.ai/brain/`.

## Incremental state
- `incremental-state.json`
- `impact.json`
- `selected-tests.json`

## Portable layer
- `index.json`
- `lookup.json`
- `symbols.json`
- `imports.json`
- `code-graph.json`
- `summary.md`

## Incremental AST
- `capabilities.json`: includes `ast_index_mode` and `ast_reparsed_files`.
- `ast-routing.json`
- `ast-symbols/<initial>.json`
- `file-outlines/<root>.json`

## Changed-symbol analysis
- `references.json`: lexical word occurrences for changed symbol definitions.
- `symbol-dependencies.json`: known symbols referenced inside a changed symbol's bounded source/AST range.

References and dependencies are static heuristics and must be source-verified.
