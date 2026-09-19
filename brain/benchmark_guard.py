#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

BRAIN = Path(".ai/brain")
BENCH = BRAIN / "benchmark.json"
OUT = BRAIN / "benchmark-health.json"

def main() -> None:
    data = json.loads(BENCH.read_text(encoding="utf-8"))
    summary = data.get("summary") or {}
    first = data.get("first_pass") or []
    cached = data.get("cached_pass") or []

    checks = {
        "all_first_pass_ok": bool(first) and all(x.get("ok") for x in first),
        "all_cached_pass_ok": bool(cached) and all(x.get("ok") for x in cached),
        "all_cached_second_pass": bool(summary.get("all_cached_second_pass")),
        "avg_selected_files_le_6": float(summary.get("avg_selected_files", 999)) <= 6.0,
        "search_index_nonempty": int(data.get("search_file_count", 0)) > 0,
        "search_tokens_nonempty": int(data.get("search_token_count", 0)) > 0,
    }
    healthy = all(checks.values())
    out = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-benchmark-health-v1",
        "healthy": healthy,
        "checks": checks,
        "observed": {
            "search_file_count": data.get("search_file_count", 0),
            "search_token_count": data.get("search_token_count", 0),
            "graph_edge_count": data.get("graph_edge_count", 0),
            "avg_selected_files": summary.get("avg_selected_files", 0),
            "first_pass_ms": summary.get("first_pass_ms", 0),
            "cached_pass_ms": summary.get("cached_pass_ms", 0),
        },
        "policy": {
            "avg_selected_files_max": 6,
            "require_second_pass_cache_hits": True,
            "timing_is_observational_only": True
        }
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not healthy:
        raise SystemExit("Repo Brain benchmark health gate failed: " + json.dumps(checks, sort_keys=True))

if __name__ == "__main__":
    main()
