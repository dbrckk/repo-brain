#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
VALIDATION = BRAIN / "validation-memory.json"

STOP = {
    "the","a","an","and","or","to","of","in","on","for","with","this","that",
    "le","la","les","un","une","des","de","du","dans","sur","pour","avec","et",
    "continue","continuer","go","fix","corrige","correction"
}

def load(default: Any) -> Any:
    try:
        return json.loads(VALIDATION.read_text(encoding="utf-8"))
    except Exception:
        return default

def dump(value: Any) -> None:
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def terms(text: str) -> list[str]:
    raw = re.findall(r"[A-Za-z0-9_.$/-]{2,}", text.lower())
    return sorted(set(x for x in raw if x not in STOP))

def record(task: str, test: str, status: str, command: str = "") -> dict[str, Any]:
    data = load({
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-validation-v1",
        "term_test_scores": {},
        "records": [],
    })
    scores = {
        token: {path: int(score) for path, score in vals.items()}
        for token, vals in (data.get("term_test_scores") or {}).items()
    }
    delta = 5 if status == "passed" else -4 if status == "failed" else 0
    for token in terms(task):
        bucket = scores.setdefault(token, {})
        bucket[test] = max(-30, min(50, bucket.get(test, 0) + delta))

    compact = {}
    for token, vals in sorted(scores.items()):
        kept = [(p, s) for p, s in vals.items() if s != 0]
        kept.sort(key=lambda x: (-abs(x[1]), x[0]))
        if kept:
            compact[token] = {p: s for p, s in kept[:32]}

    records = list(data.get("records") or [])
    records.append({
        "task": task,
        "terms": terms(task),
        "test": test,
        "status": status,
        "command": command,
    })
    records = records[-128:]

    out = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-validation-v1",
        "term_test_scores": compact,
        "records": records,
    }
    dump(out)
    return {"recorded": True, "status": status, "test": test, "record_count": len(records)}

def hints(task: str) -> dict[str, Any]:
    data = load({})
    combined: dict[str, int] = {}
    for token in terms(task):
        for path, score in ((data.get("term_test_scores") or {}).get(token) or {}).items():
            combined[path] = combined.get(path, 0) + int(score)
    items = [
        {"path": path, "score": score}
        for path, score in sorted(combined.items(), key=lambda x: (-x[1], x[0]))
        if score != 0
    ][:16]
    return {"terms": terms(task), "tests": items}

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("record")
    p.add_argument("task")
    p.add_argument("--test", required=True)
    p.add_argument("--status", required=True, choices=["passed", "failed", "skipped"])
    p.add_argument("--command", default="")

    p = sub.add_parser("hints")
    p.add_argument("task")

    args = parser.parse_args()
    if args.cmd == "record":
        out = record(args.task, args.test, args.status, args.command)
    else:
        out = hints(args.task)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
