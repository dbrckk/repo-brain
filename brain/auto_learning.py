#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
AI = Path(".ai")

NOISE_PREFIXES = (".ai/", ".github/", ".circleci/", ".repo-brain-tool/")
NOISE_FILES = {".repo-standards.yml", "AGENTS.md"}

def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def git(*args: str) -> str:
    p = subprocess.run(["git", *args], text=True, capture_output=True)
    return p.stdout.strip() if p.returncode == 0 else ""

def meaningful_task() -> str:
    session = load(AI / "session-state.json", {})
    task = str(session.get("task") or "").strip()
    if task:
        return task

    log = git("log", "-20", "--pretty=%s")
    for line in log.splitlines():
        s = line.strip()
        low = s.lower()
        if not s:
            continue
        if low.startswith(("chore(ai):", "chore: refresh repo brain", "chore(ai)", "docs(ai):")):
            continue
        return s
    return ""

def source_changes() -> list[str]:
    impact = load(BRAIN / "impact.json", {})
    out = []
    for path in impact.get("changed_source_files", []) or []:
        if not isinstance(path, str):
            continue
        if path in NOISE_FILES or path.startswith(NOISE_PREFIXES):
            continue
        out.append(path)
    return sorted(set(out))

def selected_tests() -> list[str]:
    data = load(BRAIN / "selected-tests.json", {})
    candidates = []
    for key in ("tests", "selected_tests", "files"):
        value = data.get(key)
        if isinstance(value, list):
            candidates.extend(x for x in value if isinstance(x, str))
    return sorted(set(candidates))[:32]

def routed_rejected(useful: set[str], task: str) -> list[str]:
    route = load(BRAIN / "task-route.json", {})
    if str(route.get("task") or "").strip().lower() != task.strip().lower():
        return []
    out = []
    for item in route.get("files", []) or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if isinstance(path, str) and path not in useful:
            out.append(path)
    # Automatic negative feedback is intentionally conservative.
    return sorted(set(out))[:6]

def main() -> None:
    task = meaningful_task()
    useful = source_changes()
    if not task or not useful:
        result = {
            "schema_version": 1,
            "generated_by": "dbrckk/repo-brain-auto-learning-v1",
            "learned": False,
            "reason": "missing-task-or-source-change",
            "task": task,
            "useful": useful,
        }
        (BRAIN / "auto-learning.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return

    rejected = routed_rejected(set(useful), task)
    tests = selected_tests()

    cmd = ["python3", str(Path(__file__).with_name("learning.py")), "learn", task]
    for path in useful:
        cmd += ["--useful", path]
    for path in rejected:
        cmd += ["--reject", path]
    for path in tests:
        cmd += ["--test", path]

    proc = subprocess.run(cmd, text=True, capture_output=True)
    learned = proc.returncode == 0
    payload = {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-auto-learning-v1",
        "learned": learned,
        "task": task,
        "useful": useful,
        "rejected": rejected,
        "tests_selected": tests,
        "note": "Selected tests are routing hints; this artifact does not claim they executed successfully.",
    }
    if proc.stdout.strip():
        try:
            payload["learning_result"] = json.loads(proc.stdout)
        except Exception:
            payload["learning_stdout"] = proc.stdout.strip()
    if proc.stderr.strip():
        payload["learning_stderr"] = proc.stderr.strip()[:2000]

    (BRAIN / "auto-learning.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not learned:
        raise SystemExit(payload.get("learning_stderr") or "automatic learning failed")

if __name__ == "__main__":
    main()
