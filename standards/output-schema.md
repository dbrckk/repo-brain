# Output schema

Repo Brain writes only under .ai/brain/.

- index.json: compact counts, languages, and high-density symbol files.
- symbols.json: symbol name, type, file, line, and language.
- imports.json: imports grouped by source file.
- code-graph.json: lightweight internal import edges.
- summary.md: smallest human/agent-readable entrypoint.

The graph is heuristic static analysis. It must not be treated as a runtime call graph.
