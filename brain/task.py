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
QUERY_CACHE = BRAIN / "query-cache.json"
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
    return [x for x in raw if x not in STOP]

def validation_hints(query_terms: list[str]) -> list[dict[str, Any]]:
    data = read_json(BRAIN / "validation-memory.json", {"term_test_scores": {}})
    scores: dict[str, int] = {}
    for token in query_terms:
        for path, score in ((data.get("term_test_scores") or {}).get(token) or {}).items():
            scores[path] = scores.get(path, 0) + int(score)
    return [
        {"path": path, "score": score}
        for path, score in sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        if score != 0
    ][:16]

def learning_hints(query_terms: list[str]) -> dict[str, int]:
    data = read_json(LEARNING, {"term_file_scores": {}})
    scores: dict[str, int] = {}
    for token in query_terms:
        for path, score in ((data.get("term_file_scores") or {}).get(token) or {}).items():
            scores[path] = scores.get(path, 0) + int(score)
    return scores

def search_candidates(query_terms: list[str]) -> dict[str, set[str]]:
    matches: dict[str, set[str]] = {}
    loaded: dict[str, dict[str, Any]] = {}
    for token in query_terms:
        if not token:
            continue
        shard = token[0].lower() if token[0].isalnum() else "_"
        if shard not in loaded:
            loaded[shard] = read_json(BRAIN / "search-shards" / f"{shard}.json", {"tokens": {}})
        paths = (loaded[shard].get("tokens") or {}).get(token, [])
        for path in paths:
            matches.setdefault(path, set()).add(token)
    return matches

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

def task_fingerprint(task: str) -> str:
    parts = [" ".join(terms(task))]
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
    if SESSION.is_file():
        try:
            parts.append(hashlib.sha256(SESSION.read_bytes()).hexdigest())
        except OSError:
            pass
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()

def cached_route(task: str) -> dict[str, Any] | None:
    data = read_json(QUERY_CACHE, {"entries": {}})
    fp = task_fingerprint(task)
    entry = (data.get("entries") or {}).get(fp)
    if not entry:
        return None
    route = entry.get("route")
    if isinstance(route, dict):
        out = dict(route)
        out["cache"] = {"hit": True, "fingerprint": fp}
        return out
    return None

def save_cached_route(task: str, result: dict[str, Any]) -> None:
    data = read_json(QUERY_CACHE, {"schema_version": 1, "entries": {}})
    entries = dict(data.get("entries") or {})
    fp = task_fingerprint(task)
    stored = dict(result)
    stored.pop("cache", None)
    entries[fp] = {"task": task, "route": stored}
    if len(entries) > 128:
        entries = dict(list(entries.items())[-128:])
    write_json(QUERY_CACHE, {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-query-cache-v1",
        "entries": entries,
    })

def choose_context_budget(ranked: list[dict[str, Any]], requested: int) -> dict[str, Any]:
    if not ranked:
        return {"tier": "fallback", "max_files": min(requested, 12), "confidence": "low"}
    top = ranked[0]
    top_score = int(top.get("score", 0))
    top_terms = len(top.get("matched_terms") or [])
    search_routed = "search-index" in (top.get("reasons") or [])
    second_score = int(ranked[1].get("score", 0)) if len(ranked) > 1 else 0
    margin = top_score - second_score

    if search_routed and top_terms >= 2 and top_score >= 30:
        chosen = min(requested, 3)
        confidence = "high"
        tier = "narrow"
    elif search_routed and top_score >= 17:
        chosen = min(requested, 6)
        confidence = "medium"
        tier = "bounded"
    elif top_score >= 12 and margin >= 6:
        chosen = min(requested, 6)
        confidence = "medium"
        tier = "bounded"
    else:
        chosen = min(requested, 12)
        confidence = "low"
        tier = "broad"

    return {
        "tier": tier,
        "max_files": chosen,
        "requested_max_files": requested,
        "confidence": confidence,
        "top_score": top_score,
        "score_margin": margin,
        "expand_to": min(requested, 12),
    }

def route(task: str, limit: int = 12) -> dict[str, Any]:
    cached = cached_route(task)
    if cached is not None:
        return cached
    q = terms(task)
    candidates = collect_candidates()
    for path, matched in search_candidates(q).items():
        item = candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})
        item["reasons"].append("search-index")
        item["search_terms"] = matched
    for path, learned_score in learning_hints(q).items():
        item = candidates.setdefault(path, {"path": path, "symbols": set(), "reasons": []})
        item["reasons"].append("learning")
        item["learning_score"] = learned_score
    ranked = []
    for path, item in candidates.items():
        hay = (path + " " + " ".join(item["symbols"])).lower()
        score = 0
        matched = []
        for token in q:
            if token in hay:
                score += 10 if token in path.lower() else 4
                matched.append(token)
        search_hits = set(item.get("search_terms") or set())
        if search_hits:
            score += 12 * len(search_hits)
            matched.extend(sorted(search_hits))
        if "session" in item["reasons"]:
            score += 8
        if "impact" in item["reasons"]:
            score += 6
        if "recently-changed" in item["reasons"]:
            score += 3
        if "search-index" in item["reasons"]:
            score += 5
        learned_score = int(item.get("learning_score") or 0)
        if learned_score:
            score += learned_score
        if score:
            ranked.append({
                "path": path,
                "score": score,
                "matched_terms": sorted(set(matched)),
                "reasons": sorted(set(item["reasons"])),
                "symbols": sorted(item["symbols"])[:20],
                "learning_score": learned_score,
            })
    ranked.sort(key=lambda x: (-x["score"], x["path"]))
    budget = choose_context_budget(ranked, limit)
    result = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-v8",
        "task": task,
        "terms": q,
        "budget": budget,
        "candidate_count": len(ranked),
        "files": ranked[:budget["max_files"]],
        "fallback": "If bounded context is insufficient, expand only to budget.expand_to, then use architecture/segmented maps and targeted source search.",
    }
    result["cache"] = {"hit": False, "fingerprint": task_fingerprint(task)}
    write_json(ROUTE, result)
    save_cached_route(task, result)
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
        "validated_test_hints": validation_hints(terms(task)),
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

    p = sub.add_parser("learn")
    p.add_argument("task")
    p.add_argument("--useful", action="append", default=[])
    p.add_argument("--reject", action="append", default=[])
    p.add_argument("--test", action="append", default=[])

    args = parser.parse_args()
    if args.cmd == "route":
        out = route(args.task, args.limit)
    elif args.cmd == "cache":
        out = refresh_cache(args.paths)
    elif args.cmd == "checkpoint":
        out = checkpoint(args.task, args.file, args.next, args.test)
    elif args.cmd == "learn":
        import subprocess
        cmd = ["python3", str(Path(__file__).with_name("learning.py")), "learn", args.task]
        for path in args.useful:
            cmd += ["--useful", path]
        for path in args.reject:
            cmd += ["--reject", path]
        for path in args.test:
            cmd += ["--test", path]
        proc = subprocess.run(cmd, text=True, capture_output=True)
        if proc.returncode != 0:
            raise SystemExit(proc.stderr.strip() or "learning command failed")
        out = json.loads(proc.stdout)
    else:
        out = packet(args.name, args.task, args.limit)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
