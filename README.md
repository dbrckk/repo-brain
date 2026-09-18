# repo-brain

Central code-intelligence engine for repositories using `dbrckk/repo-standards`.

## v6

Repo Brain v6 adds a task-context layer on top of the v5 indexes. The goal is to avoid broad repository exploration for routine development work.

### Task router

```text
python brain/task.py route "fix inventory menu crash"
```

The router combines the current session, recent impact data, portable symbol lookup and code-graph paths, ranks likely files, and writes:

- `.ai/brain/task-route.json`

The default context budget is 12 files and can be changed with `--limit`.

### Context packets

```text
python brain/task.py packet gameplay "fix player death handling"
```

Packets are written under:

- `.ai/brain/context/<name>.json`

A packet contains the ranked files plus current impact and selected-test data.

### Hash cache

```text
python brain/task.py cache app/src/main/Foo.kt app/src/main/Bar.kt
```

The cache stores SHA-256 plus file size in:

- `.ai/brain/hash-cache.json`

Unchanged files are reported as reused so downstream tooling can skip reparsing or resummarizing them.

### Session checkpoint

```text
python brain/task.py checkpoint "finish save system" \
  --file app/src/main/SaveManager.kt \
  --test app/src/test/SaveManagerTest.kt \
  --next "fix failing migration test"
```

The checkpoint is stored in:

- `.ai/session-state.json`

Agents should read it before reconstructing project state from broader indexes.

### v6 query CLI

```text
python brain/query.py route
python brain/query.py session
python brain/query.py packet gameplay
```

### Recommended v6 reading order

1. `.ai/session-state.json`
2. `.ai/brain/task-route.json`
3. selected context packet, when present
4. `.ai/brain/impact.json`
5. `.ai/brain/selected-tests.json`
6. exact source files from the route
7. architecture/maps only if the route is insufficient
8. broad repository exploration only as a fallback

## v5

Repo Brain v5 adds incremental AST refresh plus changed-symbol references.

### Incremental AST

When Repo Brain is already indexed, ast-grep Outline runs only on `.ai/brain/impact.json -> changed_source_files`. Existing AST shards are merged with refreshed files. Full AST rebuild remains the fallback.

### v5 outputs

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

v6 retains v5 incremental portable indexing, impact analysis, targeted test selection, ast-grep shards, changed-symbol routing and full-rebuild fallback.
