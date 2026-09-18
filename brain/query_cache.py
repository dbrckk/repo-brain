#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
AI = Path(".ai")
CACHE = BRAIN / "query-cache.json"

def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def normalize_task(task: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_.$/-]{2,}", task.lower()))

def context_fingerprint(task: str) -> str:
    parts = [normalize_task(task)]
    for name in [
        "incremental-state.json",
        "graph-index.json",
        "search-manifest.json",
        "semantic-index.json",
        "hash-cache.json",
    ]:
        p = BRAIN / name
        if p.is_file():
            try:
                parts.append(hashlib.sha256(p.read_bytes()).hexdigest())
            except OSError:
                pass
    session = AI / "session-state.json"
    if session.is_file():
        try:
            parts.append(hashlib.sha256(session.read_bytes()).hexdigest())
        except OSError:
            pass
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()

def get(task: str) -> dict[str, Any]:
    cache = load(CACHE, {"entries": {}})
    fp = context_fingerprint(task)
    entry = (cache.get("entries") or {}).get(fp)
    if entry:
        return {"hit": True, "fingerprint": fp, "entry": entry}
    return {"hit": False, "fingerprint": fp}

def put(task: str, route: dict[str, Any]) -> dict[str, Any]:
    cache = load(CACHE, {"schema_version": 1, "entries": {}})
    entries = dict(cache.get("entries") or {})
    fp = context_fingerprint(task)
    entries[fp] = {
        "task": task,
        "normalized_task": normalize_task(task),
        "route": route,
    }
    # Deterministic bounded cache: retain newest logical insertion order in file.
    if len(entries) > 128:
        entries = dict(list(entries.items())[-128:])
    out = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-query-cache-v1",
        "entries": entries,
    }
    dump(CACHE, out)
    return {"fingerprint": fp, "entries": len(entries)}

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("get")
    p.add_argument("task")
    p = sub.add_parser("put")
    p.add_argument("task")
    p.add_argument("route_json")
    p = sub.add_parser("fingerprint")
    p.add_argument("task")
    args = parser.parse_args()

    if args.cmd == "get":
        result = get(args.task)
    elif args.cmd == "put":
        result = put(args.task, json.loads(Path(args.route_json).read_text(encoding="utf-8")))
    else:
        result = {"fingerprint": context_fingerprint(args.task)}
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
