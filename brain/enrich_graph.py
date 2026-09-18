#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
GRAPH = BRAIN / "code-graph.json"

def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def shard_for(token: str) -> str:
    c = token[0].lower() if token else "_"
    return c if c.isalnum() else "_"

def main() -> None:
    graph = load(GRAPH, {"edges": []})
    lookup = load(BRAIN / "lookup.json", {"symbols": {}})

    edges = []
    seen = set()
    for raw in graph.get("edges", []) or []:
        if not isinstance(raw, dict):
            continue
        src = raw.get("source")
        dst = raw.get("target")
        typ = raw.get("type") or "related"
        if src and dst and src != dst:
            key = (src, dst, typ)
            if key not in seen:
                seen.add(key)
                edges.append({"source": src, "target": dst, "type": typ})

    shard_cache: dict[str, dict[str, Any]] = {}
    added = 0
    # Prefer type-like symbols. Same-package Kotlin/Java references often need
    # no import statement, so lexical symbol occurrence is a useful routing hint.
    for symbol, defs in sorted((lookup.get("symbols") or {}).items()):
        if not symbol or len(symbol) < 4 or not symbol[0].isupper():
            continue
        if not isinstance(defs, list) or len(defs) != 1:
            continue
        definition = defs[0]
        if not isinstance(definition, dict):
            continue
        kind = str(definition.get("kind") or "").lower()
        if kind not in {"class", "interface", "object", "enum", "record", "struct", "type"}:
            continue
        target = definition.get("file") or definition.get("path")
        if not target:
            continue

        token = symbol.lower()
        shard = shard_for(token)
        if shard not in shard_cache:
            shard_cache[shard] = load(BRAIN / "search-shards" / f"{shard}.json", {"tokens": {}})
        refs = (shard_cache[shard].get("tokens") or {}).get(token, [])
        for source in refs[:64]:
            if source == target:
                continue
            key = (source, target, "symbol-reference")
            if key in seen:
                continue
            seen.add(key)
            edges.append({"source": source, "target": target, "type": "symbol-reference"})
            added += 1
            if len(edges) >= 20000:
                break
        if len(edges) >= 20000:
            break

    dump(GRAPH, {"edges": edges})
    dump(BRAIN / "graph-enrichment.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-symbol-reference-v1",
        "base_edge_count": len(edges) - added,
        "symbol_reference_edges_added": added,
        "edge_count": len(edges),
        "method": "unique type symbol occurrences from persistent search shards",
        "warning": "Static lexical routing hint; verify authoritative source before edits.",
    })

if __name__ == "__main__":
    main()
