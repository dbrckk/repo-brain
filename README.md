# repo-brain

Central code-intelligence engine for repositories using `dbrckk/repo-standards`.

## v5

Repo Brain v5 adds incremental AST refresh plus changed-symbol references.

### Incremental AST
When Repo Brain is already indexed, ast-grep Outline runs only on `.ai/brain/impact.json -> changed_source_files`. Existing AST shards are merged with refreshed files. Full AST rebuild remains the fallback.

### New outputs
- `.ai/brain/references.json`: lexical occurrences for symbols defined in changed source files.
- `.ai/brain/symbol-dependencies.json`: bounded static dependencies inside each changed symbol's source range.

These are heuristics, not semantic compiler/LSP references.

### Query CLI
```text
python brain/query.py symbol ProviderSpec
python brain/query.py references ProviderSpec
python brain/query.py dependencies ProviderSpec
python brain/query.py impact
python brain/query.py tests
```

v5 retains v4 incremental portable indexing, impact analysis, targeted test selection, ast-grep shards, and full-rebuild fallback.
