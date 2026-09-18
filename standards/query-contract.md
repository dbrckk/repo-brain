# Repo Brain query contract

Recommended sequence:
1. Read `.ai/brain/impact.json`.
2. Read `.ai/brain/selected-tests.json`.
3. For named symbols, prefer AST shards.
4. Use `.ai/brain/references.json` to locate changed-symbol occurrences.
5. Use `.ai/brain/symbol-dependencies.json` for bounded dependency hints.
6. Fall back to portable lookup/graph and then broader repository context.

CLI:
```text
python brain/query.py symbol <name>
python brain/query.py references <name>
python brain/query.py dependencies <name>
python brain/query.py impact
python brain/query.py tests
```

All reference/dependency results are routing hints, not semantic guarantees.
