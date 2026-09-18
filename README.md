# repo-brain

Central code-intelligence engine for repositories using `dbrckk/repo-standards`.

## v4

Repo Brain v4 adds incremental indexing, change impact analysis, targeted test selection, and a compact query CLI on top of the v3 AST routing layer.

Generated context:

```text
.ai/brain/
├── summary.md
├── incremental-state.json
├── impact.json
├── selected-tests.json
├── capabilities.json
├── index.json
├── lookup.json
├── symbols.json
├── imports.json
├── code-graph.json
├── ast-routing.json
├── ast-symbols/
│   ├── a.json
│   ├── p.json
│   └── ...
└── file-outlines/
    ├── src.json
    ├── tests.json
    └── ...
```

## Incremental indexing

The first run performs a full portable rebuild. Later runs reuse the previous committed index when the stored `indexed_head` is still an ancestor of the current commit.

For a small diff Repo Brain:

1. removes stale symbols/imports for changed or deleted files;
2. reparses only changed source files;
3. rebuilds the lightweight relationship graph from the merged index;
4. writes `impact.json`;
5. selects likely tests in `selected-tests.json`.

A full rebuild is used automatically when the previous state is unavailable, divergent, or the change set is too large.

## Routing

For a named symbol such as `ProviderSpec`:

1. read `.ai/brain/capabilities.json`;
2. when ast-grep enrichment is available, route through `.ai/brain/ast-routing.json`;
3. open one symbol shard, for example `.ai/brain/ast-symbols/p.json`;
4. use the exact file and start/end range;
5. verify the authoritative source before editing.

When AST routing has no useful hit, fall back to `.ai/brain/lookup.json`.

## Impact and tests

Read `.ai/brain/impact.json` before broad exploration. It records changed source files, likely reverse-import impact, impacted symbols, and test candidates.

Read `.ai/brain/selected-tests.json` before running the full suite. Its commands are targeted candidates and should be verified against the repository's canonical test tooling.

## Query CLI

When the Repo Brain tool checkout is available:

```text
python brain/query.py symbol ProviderSpec
python brain/query.py impact
python brain/query.py tests
```

Repo Brain never treats static relationships as proof of runtime behavior.
