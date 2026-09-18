#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

BRAIN = Path(".ai/brain")
SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".kt", ".kts", ".gd", ".rs", ".go"
}
MAX_SYMBOLS = 80
MAX_REFS_PER_SYMBOL = 120
MAX_DEPS_PER_SYMBOL = 40

def load(path, default):
    try:
        return json.loads((BRAIN / path).read_text())
    except Exception:
        return default

def git_grep_word(name):
    p = subprocess.run(
        ["git", "grep", "-n", "-w", "-e", name, "--", ".", ":(exclude).ai/**", ":(exclude).repo-brain-tool/**"],
        text=True, capture_output=True
    )
    if p.returncode not in (0, 1):
        return []
    out = []
    for line in p.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, lineno, text = parts
        if Path(path).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            lineno = int(lineno)
        except ValueError:
            continue
        out.append({"file": path, "line": lineno, "preview": text.strip()[:180]})
        if len(out) >= MAX_REFS_PER_SYMBOL:
            break
    return out

def ast_ranges_for(name):
    if not name:
        return []
    shard = name[0].lower() if name[0].isalnum() else "_"
    data = load(f"ast-symbols/{shard}.json", {"symbols": {}})
    return (data.get("symbols") or {}).get(name, [])

impact = load("impact.json", {})
lookup = load("lookup.json", {"symbols": {}}).get("symbols") or {}
symbols = load("symbols.json", {"symbols": []}).get("symbols") or []
changed_source = set(impact.get("changed_source_files") or [])

changed_defs = []
seen = set()
for s in symbols:
    if s.get("file") not in changed_source:
        continue
    name = s.get("name")
    if not name or name in seen:
        continue
    seen.add(name)
    changed_defs.append(s)
    if len(changed_defs) >= MAX_SYMBOLS:
        break

references = {}
dependencies = {}

known_names = set(lookup.keys())

for sym in changed_defs:
    name = sym["name"]
    refs = git_grep_word(name)
    for ref in refs:
        ref["definition_candidate"] = (
            ref["file"] == sym.get("file") and ref["line"] == sym.get("line")
        )
    references[name] = {
        "definition": {
            "file": sym.get("file"),
            "line": sym.get("line"),
            "kind": sym.get("kind"),
            "language": sym.get("language"),
        },
        "occurrences": refs,
        "occurrence_count": len(refs),
    }

    # Prefer exact AST range, then fall back to a bounded region after definition.
    ranges = [
        r for r in ast_ranges_for(name)
        if r.get("file") == sym.get("file") and r.get("start")
    ]
    if ranges:
        start = int(ranges[0].get("start"))
        end = int(ranges[0].get("end") or start)
    else:
        start = int(sym.get("line") or 1)
        end = start + 120

    try:
        lines = Path(sym["file"]).read_text(errors="ignore").splitlines()
        snippet = "\n".join(lines[max(0, start - 1):min(len(lines), end)])
    except Exception:
        snippet = ""

    candidates = []
    if snippet:
        words = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", snippet))
        for dep_name in sorted(words & known_names):
            if dep_name == name:
                continue
            defs = lookup.get(dep_name) or []
            candidates.append({
                "symbol": dep_name,
                "definitions": defs[:5],
            })
            if len(candidates) >= MAX_DEPS_PER_SYMBOL:
                break

    dependencies[name] = {
        "source": {
            "file": sym.get("file"),
            "start": start,
            "end": end,
        },
        "symbol_dependencies": candidates,
        "dependency_count": len(candidates),
    }

(BRAIN / "references.json").write_text(json.dumps({
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "scope": "symbols defined in changed source files",
    "semantic": False,
    "note": "Occurrences are lexical word matches; verify source/LSP/compiler data before relying on them.",
    "symbols": references,
}, indent=2) + "\n")

(BRAIN / "symbol-dependencies.json").write_text(json.dumps({
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "scope": "symbols defined in changed source files",
    "semantic": False,
    "note": "Dependencies are known symbol names lexically present inside the symbol's AST/source range.",
    "symbols": dependencies,
}, indent=2) + "\n")
