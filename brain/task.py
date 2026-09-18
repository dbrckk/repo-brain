#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
AI = Path(".ai")
SESSION = AI / "session-state.json"
ROUTE = BRAIN / "task-route.json"
CACHE = BRAIN / "hash-cache.json"

STOP = {
    "the","a","an","and","or","to","of","in","on","for","with","this","that",
    "le","la","les","un","une","des","de","du","dans","sur","pour","avec","et",
    "continue","continuer","go","fix","corrige","correction"
}

def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def terms(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9_.$/-]{2,}", text.lower())
    return [x for x in raw if x not in STOP]

def collect_candidates() -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    lookup = read_json(BRAIN / "lookup.json", {})
    for name, entries in (lookup.get("symbols") or {}).items():
        for entry in entries or []:
            path = entry.get("path") or entry.get("file")
            if not path:
                continue
            item = candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})
            item["symbols"].add(name)

    graph = read_json(BRAIN / "code-graph.json", {})
    for node in graph.get("nodes", []) or []:
        path = node.get("path") or node.get("file")
        if path:
            candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})

    impact = read_json(BRAIN / "impact.json", {})
    for item in impact.get("changed_files", []) or []:
        path = item.get("path")
        if path:
            c = candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})
            c["reasons"].append("recently-changed")
    for path in impact.get("impacted_files", []) or []:
        if isinstance(path, dict):
            path = path.get("path")
        if path:
            c = candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})
            c["reasons"].append("impact")

    session = read_json(SESSION, {})
    for path in session.get("files", []) or []:
        c = candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})
        c["reasons"].append("session")

    return candidates

def route(task: str, limit: int = 12) -> dict[str, Any]:
    q = terms(task)
    candidates = collect_candidates()
    ranked = []
    for path, item in candidates.items():
        hay = (path + " " + " ".join(item["symbols"])).lower()
        score = 0
        matched = []
        for token in q:
            if token in hay:
                score += 10 if token in path.lower() else 4
                matched.append(token)
        if "session" in item["reasons"]:
            score += 8
        if "impact" in item["reasons"]:
            score += 6
        if "recently-changed" in item["reasons"]:
            score += 3
        if score:
            ranked.append({
                "path": path,
                "score": score,
                "matched_terms": sorted(set(matched)),
                "reasons": sorted(set(item["reasons"])),
                "symbols": sorted(item["symbols"])[:20],
            })
    ranked.sort(key=lambda x: (-x["score"], x["path"]))
    result = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v6",
        "task": task,
        "terms": q,
        "budget": {"max_files": limit},
        "files": ranked[:limit],
        "fallback": "Use architecture/segmented maps, then targeted source search if files are insufficient.",
    }
    write_json(ROUTE, result)
    return result

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def refresh_cache(paths: list[str]) -> dict[str, Any]:
    previous = read_json(CACHE, {"files": {}})
    files = dict(previous.get("files") or {})
    changed, reused, missing = [], [], []
    for raw in paths:
        p = Path(raw)
        if not p.is_file():
            missing.append(raw)
            continue
        digest = hash_file(p)
        old = (files.get(raw) or {}).get("sha256")
        if old == digest:
            reused.append(raw)
        else:
            changed.append(raw)
        files[raw] = {"sha256": digest, "size": p.stat().st_size}
    out = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v6",
        "files": files,
        "last_refresh": {"changed": changed, "reused": reused, "missing": missing},
    }
    write_json(CACHE, out)
    return out["last_refresh"]

def checkpoint(task: str, files: list[str], next_action: str = "", tests: list[str] | None = None) -> dict[str, Any]:
    old = read_json(SESSION, {})
    out = {
        "schema_version": 1,
        "task": task or old.get("task", ""),
        "files": sorted(set(files or old.get("files", []))),
        "tests": tests if tests is not None else old.get("tests", []),
        "next_action": next_action or old.get("next_action", ""),
    }
    write_json(SESSION, out)
    return out

def packet(name: str, task: str, limit: int = 12) -> dict[str, Any]:
    r = route(task, limit)
    out = {
        "schema_version": 1,
        "name": name,
        "task": task,
        "files": r["files"],
        "impact": read_json(BRAIN / "impact.json", {}),
        "selected_tests": read_json(BRAIN / "selected-tests.json", {}),
    }
    target = BRAIN / "context" / f"{name}.json"
    write_json(target, out)
    return {"path": str(target), "file_count": len(out["files"])}

def main() -> None:
    parser = argparse.ArgumentParser(description="Repo Brain v6 task-context utilities")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("route")
    p.add_argument("task")
    p.add_argument("--limit", type=int, default=12)

    p = sub.add_parser("cache")
    p.add_argument("paths", nargs="+")

    p = sub.add_parser("checkpoint")
    p.add_argument("task")
    p.add_argument("--file", action="append", default=[])
    p.add_argument("--test", action="append", default=[])
    p.add_argument("--next", default="")

    p = sub.add_parser("packet")
    p.add_argument("name")
    p.add_argument("task")
    p.add_argument("--limit", type=int, default=12)

    args = parser.parse_args()
    if args.cmd == "route":
        out = route(args.task, args.limit)
    elif args.cmd == "cache":
        out = refresh_cache(args.paths)
    elif args.cmd == "checkpoint":
        out = checkpoint(args.task, args.file, args.next, args.test)
    else:
        out = packet(args.name, args.task, args.limit)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
