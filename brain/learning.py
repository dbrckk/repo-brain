#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
LEARNING = BRAIN / "routing-learning.json"

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
    return sorted(set(x for x in raw if x not in STOP))

def learn(task: str, useful: list[str], rejected: list[str], tests: list[str]) -> dict[str, Any]:
    data = read_json(LEARNING, {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-learning-v1",
        "term_file_scores": {},
        "term_test_scores": {},
        "examples": [],
    })
    file_scores: dict[str, dict[str, int]] = {
        k: {p: int(v) for p, v in vals.items()}
        for k, vals in (data.get("term_file_scores") or {}).items()
    }
    test_scores: dict[str, dict[str, int]] = {
        k: {p: int(v) for p, v in vals.items()}
        for k, vals in (data.get("term_test_scores") or {}).items()
    }

    task_terms = terms(task)
    for token in task_terms:
        fs = file_scores.setdefault(token, {})
        for path in useful:
            fs[path] = max(-20, min(40, fs.get(path, 0) + 4))
        for path in rejected:
            fs[path] = max(-20, min(40, fs.get(path, 0) - 2))

        ts = test_scores.setdefault(token, {})
        for path in tests:
            ts[path] = max(0, min(40, ts.get(path, 0) + 3))

    # Prune zero entries and keep bounded maps.
    compact_files = {}
    for token, scores in sorted(file_scores.items()):
        kept = [(p, s) for p, s in scores.items() if s != 0]
        kept.sort(key=lambda x: (-abs(x[1]), x[0]))
        if kept:
            compact_files[token] = {p: s for p, s in kept[:64]}

    compact_tests = {}
    for token, scores in sorted(test_scores.items()):
        kept = [(p, s) for p, s in scores.items() if s > 0]
        kept.sort(key=lambda x: (-x[1], x[0]))
        if kept:
            compact_tests[token] = {p: s for p, s in kept[:32]}

    examples = list(data.get("examples") or [])
    examples.append({
        "task": task,
        "terms": task_terms,
        "useful": sorted(set(useful)),
        "rejected": sorted(set(rejected)),
        "tests": sorted(set(tests)),
    })
    examples = examples[-64:]

    out = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-learning-v1",
        "term_file_scores": compact_files,
        "term_test_scores": compact_tests,
        "examples": examples,
    }
    write_json(LEARNING, out)
    return {
        "terms": task_terms,
        "useful_count": len(set(useful)),
        "rejected_count": len(set(rejected)),
        "test_count": len(set(tests)),
        "example_count": len(examples),
    }

def hints(task: str) -> dict[str, Any]:
    data = read_json(LEARNING, {})
    file_scores: dict[str, int] = defaultdict(int)
    test_scores: dict[str, int] = defaultdict(int)
    task_terms = terms(task)

    for token in task_terms:
        for path, score in ((data.get("term_file_scores") or {}).get(token) or {}).items():
            file_scores[path] += int(score)
        for path, score in ((data.get("term_test_scores") or {}).get(token) or {}).items():
            test_scores[path] += int(score)

    files = [
        {"path": p, "score": s}
        for p, s in sorted(file_scores.items(), key=lambda x: (-x[1], x[0]))
        if s != 0
    ][:32]
    tests = [
        {"path": p, "score": s}
        for p, s in sorted(test_scores.items(), key=lambda x: (-x[1], x[0]))
        if s > 0
    ][:16]
    return {"terms": task_terms, "files": files, "tests": tests}

def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("learn")
    p.add_argument("task")
    p.add_argument("--useful", action="append", default=[])
    p.add_argument("--reject", action="append", default=[])
    p.add_argument("--test", action="append", default=[])

    p = sub.add_parser("hints")
    p.add_argument("task")

    args = parser.parse_args()
    if args.cmd == "learn":
        out = learn(args.task, args.useful, args.reject, args.test)
    else:
        out = hints(args.task)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
