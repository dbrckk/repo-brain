# repo-brain

Central code-intelligence engine for repositories using `dbrckk/repo-standards`.

## v4

Repo Brain v4 adds incremental indexing, impact analysis, targeted test selection, and a small query CLI.

### Incremental mode

Repo Brain stores its previous indexed commit in:

```text
.ai/brain/incremental-state.json
```

On the next run it:

1. compares the previous indexed commit with the current HEAD;
2. removes stale symbol/import entries for changed or deleted files;
3. reparses only changed source files;
4. rebuilds derived lookup/graph outputs from the merged state;
5. falls back to a full rebuild when history is unavailable, divergent, or the change set is too large.

### New outputs

```text
.ai/brain/
├── incremental-state.json
├── impact.json
├── selected-tests.json
├── summary.md
├── capabilities.json
├── index.json
├── lookup.json
├── symbols.json
├── imports.json
├── code-graph.json
├── ast-routing.json
├── ast-symbols/
└── file-outlines/
```

### Impact

`impact.json` records:

- changed files;
- changed source files;
- files that statically depend on changed source;
- symbols in affected files;
- test candidates.

### Targeted tests

`selected-tests.json` contains the smallest detected test set and candidate commands.

For Python repositories, Repo Brain can generate a command such as:

```text
python -m pytest tests/test_provider_router.py
```

When confidence is insufficient, agents must fall back to the repository's canonical validation commands.

### Query CLI

```text
python brain/query.py symbol ProviderSpec
python brain/query.py impact
python brain/query.py tests
```

The CLI is intentionally small and returns only the requested routing data.

## AST routing

Repo Brain still uses optional ast-grep Outline enrichment for exact symbol/member ranges when supported. The portable index remains the fallback.

For a symbol such as `ProviderSpec`:

1. read `.ai/brain/capabilities.json`;
2. if `ast_grep_outline` is true, route through `.ai/brain/ast-routing.json`;
3. open one `.ai/brain/ast-symbols/<initial>.json` shard;
4. use the exact source range;
5. verify authoritative source before editing.
