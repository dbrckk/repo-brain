# Repo Brain query contract

Agents should use Repo Brain as a routing index, not as a replacement for source verification.

Recommended sequence:

1. Read `.ai/brain/summary.md`.
2. Read `.ai/brain/impact.json`.
3. Read `.ai/brain/selected-tests.json`.
4. For a named symbol, prefer AST shard routing when `.ai/brain/capabilities.json` says it is available.
5. Fall back to `.ai/brain/lookup.json`.
6. Read only the matching source file and exact/nearby lines.
7. Use `.ai/brain/imports.json` and `.ai/brain/code-graph.json` when the change crosses modules.
8. Fall back to segmented/full repository maps only when symbol-level context is insufficient.

The query CLI exposes the same contract:

```text
python brain/query.py symbol <name>
python brain/query.py impact
python brain/query.py tests
```

A symbol hit, impact edge, or selected test is a locator/hint. Source and canonical project tooling remain authoritative.
