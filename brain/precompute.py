#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
CONTEXT = BRAIN / "context"

def load(name: str, default: Any) -> Any:
    try:
        return json.loads((BRAIN / name).read_text(encoding="utf-8"))
    except Exception:
        return default

def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def norm_path(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("path") or value.get("file") or value.get("filename")
    return None

def score_paths() -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}

    def add(path: str | None, score: int, reason: str) -> None:
        if not path:
            return
        item = scores.setdefault(path, {"path": path, "score": 0, "reasons": []})
        item["score"] += score
        item["reasons"].append(reason)

    impact = load("impact.json", {})
    for item in impact.get("changed_files", []) or []:
        add(norm_path(item), 100, "changed")
    for item in impact.get("changed_source_files", []) or []:
        add(norm_path(item), 120, "changed-source")
    for item in impact.get("impacted_files", []) or []:
        add(norm_path(item), 80, "impact")
    for item in impact.get("selected_tests", []) or []:
        add(norm_path(item), 70, "selected-test")

    selected = load("selected-tests.json", {})
    for key in ("tests", "files", "selected_tests"):
        for item in selected.get(key, []) or []:
            add(norm_path(item), 70, "selected-test")

    graph = load("code-graph.json", {})
    edges = graph.get("edges", []) or []
    hot_seeds = set(scores)
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = edge.get("source") or edge.get("from") or edge.get("src")
        dst = edge.get("target") or edge.get("to") or edge.get("dst")
        if src in hot_seeds:
            add(dst, 25, "dependency-neighbor")
        if dst in hot_seeds:
            add(src, 30, "reverse-dependency-neighbor")

    lookup = load("lookup.json", {})
    for _, entries in (lookup.get("symbols") or {}).items():
        for entry in entries or []:
            path = norm_path(entry)
            if path in hot_seeds:
                add(path, 5, "symbol-indexed")

    useful = [p for p in scores if not is_noise(p)]
    if len(useful) < 8:
        for path in recent_project_files():
            if not is_noise(path):
                add(path, 60, "recent-project-state")

    architecture = Path(".ai/architecture.json")
    if architecture.is_file():
        try:
            data = json.loads(architecture.read_text(encoding="utf-8"))
            for path in data.get("entrypoint_candidates", []) or []:
                if isinstance(path, str) and not is_noise(path):
                    add(path, 40, "entrypoint")
        except Exception:
            pass

    return scores

def area_for(path: str) -> str:
    parts = [p for p in Path(path).parts if p not in (".", "")]
    if not parts:
        return "root"
    first = parts[0].lstrip(".") or "root"
    if first in {"src", "app", "lib", "packages", "modules"} and len(parts) > 1:
        return "-".join([first, parts[1]]).replace("_", "-").lower()
    return first.replace("_", "-").lower()

def is_noise(path: str) -> bool:
    p = path.lower()
    noise_prefixes = (
        ".ai/", ".github/", ".circleci/", ".serena/", "art/", "marketing/",
        "docs/", "build/", "dist/", "vendor/", "node_modules/"
    )
    noise_suffixes = (
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
        ".lock", ".map"
    )
    return p.startswith(noise_prefixes) or p.endswith(noise_suffixes) or p == ".repo-standards.yml"

def recent_project_files() -> list[str]:
    state = Path(".ai/project-state.md")
    if not state.is_file():
        return []
    try:
        text = state.read_text(encoding="utf-8")
    except OSError:
        return []
    files = []
    in_recent = False
    for line in text.splitlines():
        if line.strip() == "### Recently changed files":
            in_recent = True
            continue
        if in_recent and line.startswith("### "):
            break
        if in_recent:
            m = re.match(r"- `(.+?)`", line.strip())
            if m:
                files.append(m.group(1))
    return files

def digest(path: str) -> dict[str, Any] | None:
    p = Path(path)
    if not p.is_file():
        return None
    h = hashlib.sha256()
    try:
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return {"sha256": h.hexdigest(), "size": p.stat().st_size}
    except OSError:
        return None

def main() -> None:
    scored = score_paths()
    ranked = sorted(scored.values(), key=lambda x: (-x["score"], x["path"]))[:32]
    for item in ranked:
        item["reasons"] = sorted(set(item["reasons"]))

    hotset = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v6",
        "max_files": 32,
        "files": ranked,
    }
    dump(BRAIN / "hotset.json", hotset)

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in ranked:
        groups[area_for(item["path"])].append(item)

    CONTEXT.mkdir(parents=True, exist_ok=True)
    for old in CONTEXT.glob("*.json"):
        old.unlink()

    manifest = []
    for area, items in sorted(groups.items()):
        packet = {
            "schema_version": 1,
            "generated_by": "dbrckk/repo-brain-v6",
            "area": area,
            "files": items[:16],
        }
        target = CONTEXT / f"{area}.json"
        dump(target, packet)
        manifest.append({"area": area, "path": str(target), "file_count": len(packet["files"])})

    dump(BRAIN / "context-manifest.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v6",
        "packets": manifest,
    })

    hashes = {}
    for item in ranked:
        meta = digest(item["path"])
        if meta:
            hashes[item["path"]] = meta
    dump(BRAIN / "hash-cache.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v6",
        "scope": "hotset",
        "files": hashes,
    })

if __name__ == "__main__":
    main()
