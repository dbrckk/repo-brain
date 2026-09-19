#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

BRAIN = Path(".ai/brain")
OUT = BRAIN / "benchmark.json"

TASKS = [
    "purchase billing",
    "income progression",
    "privacy consent",
    "offline progress",
    "game engine",
]

def run_task(task: str) -> dict:
    start = time.perf_counter()
    p = subprocess.run(
        ["python3", ".repo-brain-tool/brain/task.py", "route", task],
        text=True,
        capture_output=True,
    )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    if p.returncode != 0:
        return {"task": task, "ok": False, "elapsed_ms": elapsed_ms, "error": p.stderr[-1000:]}
    data = json.loads(p.stdout)
    return {
        "task": task,
        "ok": True,
        "elapsed_ms": elapsed_ms,
        "candidate_count": data.get("candidate_count", 0),
        "selected_files": len(data.get("files") or []),
        "budget": data.get("budget") or {},
        "cache_hit": bool((data.get("cache") or {}).get("hit")),
    }

def main() -> None:
    first = [run_task(t) for t in TASKS]
    second = [run_task(t) for t in TASKS]
    manifest = {}
    try:
        manifest = json.loads((BRAIN / "search-manifest.json").read_text())
    except Exception:
        pass
    graph = {}
    try:
        graph = json.loads((BRAIN / "graph-enrichment.json").read_text())
    except Exception:
        pass

    out = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-benchmark-v1",
        "search_file_count": manifest.get("file_count", 0),
        "search_token_count": manifest.get("token_count", 0),
        "graph_edge_count": graph.get("edge_count", 0),
        "first_pass": first,
        "cached_pass": second,
        "summary": {
            "first_pass_ms": round(sum(x["elapsed_ms"] for x in first), 3),
            "cached_pass_ms": round(sum(x["elapsed_ms"] for x in second), 3),
            "avg_selected_files": round(sum(x.get("selected_files",0) for x in first) / max(1,len(first)), 2),
            "all_cached_second_pass": all(x.get("cache_hit") for x in second if x.get("ok")),
        },
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
