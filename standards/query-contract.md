# Repo Brain query contract

Agents should use Repo Brain as a routing index, not as a replacement for source verification.

Recommended lookup sequence:

1. Read .ai/brain/summary.md.
2. Search .ai/brain/symbols.json for the requested class/function/symbol.
3. Read only the matching source file and nearby lines.
4. Use .ai/brain/imports.json and .ai/brain/code-graph.json when the change crosses modules.
5. Fall back to .ai/maps/ or .ai/repo-map.md only when symbol-level context is insufficient.

A symbol hit should be treated as a locator. The source file remains authoritative.
