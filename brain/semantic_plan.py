#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")

def dump(name: str, value: Any) -> None:
    BRAIN.mkdir(parents=True, exist_ok=True)
    (BRAIN / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def exists_any(patterns: list[str]) -> bool:
    for pattern in patterns:
        if any(Path(".").glob(pattern)):
            return True
    return False

def main() -> None:
    modes = []
    if exists_any(["pyproject.toml", "setup.py", "setup.cfg", "**/pyproject.toml"]):
        modes.append({
            "language": "python",
            "indexer": "scip-python",
            "status": "eligible",
            "cost": "medium",
            "command": "npx -y @sourcegraph/scip-python index . --project-name=repo-brain-project",
        })
    if exists_any(["tsconfig.json", "**/tsconfig.json"]):
        modes.append({
            "language": "typescript",
            "indexer": "scip-typescript",
            "status": "eligible",
            "cost": "medium",
            "command": "npx -y @sourcegraph/scip-typescript index",
        })
    if exists_any(["build.gradle", "build.gradle.kts", "pom.xml"]):
        modes.append({
            "language": "java-kotlin",
            "indexer": "scip-java",
            "status": "deferred-build-aware",
            "cost": "high",
            "command": "scip-java index",
            "reason": "SCIP Java/Kotlin indexing invokes the project build; do not run on every context refresh.",
        })
    if exists_any(["go.mod", "**/go.mod"]):
        modes.append({
            "language": "go",
            "indexer": "scip-go",
            "status": "eligible",
            "cost": "medium",
            "command": "scip-go",
        })
    if exists_any(["Cargo.toml", "**/Cargo.toml"]):
        modes.append({
            "language": "rust",
            "indexer": "rust-analyzer",
            "status": "eligible",
            "cost": "medium",
            "command": "rust-analyzer scip .",
        })

    dump("semantic-plan.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-semantic",
        "scip": {
            "enabled_by_default": False,
            "modes": modes,
            "policy": "Generate precise SCIP only in a dedicated semantic refresh; keep routine context refresh fast.",
        },
        "zoekt": {
            "mode": "external-persistent-index",
            "enabled_in_push_workflow": False,
            "reason": "Zoekt is most useful with a persistent index/service; rebuilding it on every push defeats the latency goal.",
        },
        "fallback_order": [
            "existing semantic-index.json",
            "ast-grep",
            "portable symbol lookup",
            "compact graph",
            "targeted text search",
        ],
    })

if __name__ == "__main__":
    main()
