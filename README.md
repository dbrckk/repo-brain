# repo-brain

Central code-intelligence engine for repositories using `dbrckk/repo-standards`.

## v3

Repo Brain v3 combines two layers:

1. A portable built-in indexer that works without external parsing tools.
2. Optional ast-grep Outline enrichment for exact symbol/member ranges when supported.

Generated context:

```text
.ai/brain/
├── summary.md
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

## Routing

For a named symbol such as `ProviderSpec`:

1. Read `.ai/brain/capabilities.json`.
2. If `ast_grep_outline` is true, read `.ai/brain/ast-routing.json`.
3. Lowercase the first symbol character and open that shard, for example `.ai/brain/ast-symbols/p.json`.
4. Use the exact file and start/end line range from that entry.
5. Verify the authoritative source before editing.

When ast-grep is unavailable or has no useful entry, fall back to `.ai/brain/lookup.json`.

Repo Brain never treats static relationships as proof of runtime behavior.
