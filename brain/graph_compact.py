#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
SHARDS = BRAIN / "graph-shards"

def load(name: str, default: Any) -> Any:
    try:
        return json.loads((BRAIN / name).read_text(encoding="utf-8"))
    except Exception:
        return default

def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def area(path: str) -> str:
    parts = [p for p in Path(path).parts if p not in ("", ".")]
    if not parts:
        return "root"
    first = parts[0].lstrip(".") or "root"
    if first in {"app", "src", "lib", "packages", "modules", "tools"} and len(parts) > 1:
        return "-".join([first, parts[1]]).replace("_", "-").lower()
    return first.replace("_", "-").lower()

def main() -> None:
    graph = load("code-graph.json", {"edges": []})
    edges = []
    forward: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    by_area: dict[str, list[dict[str, str]]] = defaultdict(list)

    for raw in graph.get("edges", []) or []:
        if not isinstance(raw, dict):
            continue
        src = raw.get("source") or raw.get("from") or raw.get("src")
        dst = raw.get("target") or raw.get("to") or raw.get("dst")
        typ = raw.get("type") or "related"
        if not src or not dst or src == dst:
            continue
        edge = {"source": src, "target": dst, "type": typ}
        edges.append(edge)
        forward[src].add(dst)
        reverse[dst].add(src)
        by_area[area(src)].append(edge)
        if area(dst) != area(src):
            by_area[area(dst)].append(edge)

    nodes = sorted(set(forward) | set(reverse))
    reverse_index = {
        node: {
            "dependents": sorted(reverse.get(node, set())),
            "dependencies": sorted(forward.get(node, set())),
            "in_degree": len(reverse.get(node, set())),
            "out_degree": len(forward.get(node, set())),
        }
        for node in nodes
    }

    ranked = sorted(
        (
            {"path": n, **reverse_index[n]}
            for n in nodes
        ),
        key=lambda x: (-(x["in_degree"] + x["out_degree"]), -x["in_degree"], x["path"]),
    )

    dump(BRAIN / "reverse-deps.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v7-graph",
        "files": reverse_index,
    })

    dump(BRAIN / "graph-index.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v7-graph",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "areas": sorted(by_area),
        "central_files": ranked[:64],
    })

    SHARDS.mkdir(parents=True, exist_ok=True)
    for old in SHARDS.glob("*.json"):
        old.unlink()
    manifest = []
    for name, area_edges in sorted(by_area.items()):
        dedup = {
            (e["source"], e["target"], e["type"]): e
            for e in area_edges
        }
        payload = {
            "schema_version": 1,
            "area": name,
            "edges": [dedup[k] for k in sorted(dedup)],
        }
        target = SHARDS / f"{name}.json"
        dump(target, payload)
        manifest.append({
            "area": name,
            "path": str(target),
            "edge_count": len(payload["edges"]),
        })

    dump(BRAIN / "graph-manifest.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v7-graph",
        "shards": manifest,
    })

    # Compact Mermaid is optional human-readable output; JSON remains authoritative.
    mmd = ["flowchart LR"]
    for edge in edges[:200]:
        def ident(p: str) -> str:
            import hashlib
            return "n" + hashlib.sha1(p.encode("utf-8")).hexdigest()[:10]
        s, d = ident(edge["source"]), ident(edge["target"])
        sl = edge["source"].replace('"', "'")
        dl = edge["target"].replace('"', "'")
        mmd.append(f'  {s}["{sl}"] --> {d}["{dl}"]')
    (BRAIN / "architecture.mmd").write_text("\n".join(mmd) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
