# repo-brain

Central code-intelligence engine for repositories using dbrckk/repo-standards.

repo-standards manages repository hygiene, CI context, project state and compact maps.
repo-brain adds a smaller symbol-oriented navigation layer so AI agents can locate relevant code before reading large files.

Generated files:
.ai/brain/index.json
.ai/brain/symbols.json
.ai/brain/imports.json
.ai/brain/code-graph.json
.ai/brain/summary.md

Recommended reading order:
1. .ai/project-state.md
2. .ai/change-impact.md
3. .ai/brain/summary.md
4. .ai/brain/index.json
5. .ai/brain/code-graph.json
6. relevant source files
7. segmented/full repo maps only when needed

Reusable workflow:
dbrckk/repo-brain/.github/workflows/reusable-index.yml@v1
