# Repo Brain query contract

Agents should use Repo Brain as a routing index, not as a replacement for source verification.

Recommended sequence:

1. Read `.ai/brain/impact.json`.
2. Read `.ai/brain/selected-tests.json`.
3. Read `.ai/brain/summary.md` and `.ai/brain/capabilities.json`.
4. For a named symbol, use an AST shard when available.
5. Fall back to `.ai/brain/lookup.json`.
6. Read only the matching source file and nearby lines.
7. Use `.ai/brain/imports.json` and `.ai/brain/code-graph.json` when the change crosses modules.
8. Run targeted tests first when their confidence is sufficient.
9. Fall back to broad canonical validation when targeted selection is empty or uncertain.

The helper CLI supports:

```text
python brain/query.py symbol <name>
python brain/query.py impact
python brain/query.py tests
```

A symbol hit, impact edge, or selected test is a locator/hint. Source and project-native test configuration remain authoritative.
