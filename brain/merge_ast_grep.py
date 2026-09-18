#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BRAIN = Path(".ai/brain")
RAW = BRAIN / "ast-grep-outline.raw.json"
AST_LOOKUP = BRAIN / "ast-lookup.json"
FILE_OUTLINE = BRAIN / "file-outline.json"
CAP = BRAIN / "capabilities.json"

capabilities = {
    "schema_version": 2,
    "generated_by": "dbrckk/repo-brain",
    "portable_index": True,
    "ast_grep_outline": False,
    "ast_grep_outline_files": 0,
    "ast_grep_outline_items": 0,
    "ast_grep_member_items": 0,
}

def write_empty():
    AST_LOOKUP.write_text('{"symbols":{}}\n')
    FILE_OUTLINE.write_text('{"files":{}}\n')
    CAP.write_text(json.dumps(capabilities, indent=2) + "\n")

if not RAW.exists() or RAW.stat().st_size == 0:
    write_empty()
    raise SystemExit(0)

try:
    data = json.loads(RAW.read_text())
except Exception:
    write_empty()
    raise SystemExit(0)

if isinstance(data, dict):
    data = [data]
if not isinstance(data, list):
    data = []

lookup = defaultdict(list)
file_outline = {}
top_count = 0
member_count = 0

def loc(item):
    rng = item.get("range") or {}
    start = (rng.get("start") or {}).get("line")
    end = (rng.get("end") or {}).get("line")
    return (
        (start + 1) if isinstance(start, int) else None,
        (end + 1) if isinstance(end, int) else None,
    )

for obj in data:
    if not isinstance(obj, dict):
        continue
    path = (obj.get("path") or "").removeprefix("./")
    if not path:
        continue
    language = obj.get("language")
    compact_items = []

    for item in obj.get("items") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        typ = item.get("symbolType")
        start, end = loc(item)
        if not name:
            continue
        top_count += 1

        base = {
            "file": path,
            "type": typ,
            "start": start,
            "end": end,
        }
        if language:
            base["language"] = language
        if item.get("isExported") is not None:
            base["exported"] = bool(item.get("isExported"))
        if item.get("isImport") is not None:
            base["import"] = bool(item.get("isImport"))
        lookup[name].append({k:v for k,v in base.items() if v is not None})

        members = []
        for member in item.get("members") or []:
            if not isinstance(member, dict) or not member.get("name"):
                continue
            mstart, mend = loc(member)
            member_count += 1
            m = {
                "name": member.get("name"),
                "type": member.get("symbolType"),
                "start": mstart,
                "end": mend,
            }
            members.append({k:v for k,v in m.items() if v is not None})

            ment = {
                "file": path,
                "type": member.get("symbolType"),
                "start": mstart,
                "end": mend,
                "parent": name,
            }
            if language:
                ment["language"] = language
            lookup[member["name"]].append({k:v for k,v in ment.items() if v is not None})

        item_compact = {
            "name": name,
            "type": typ,
            "start": start,
            "end": end,
        }
        if members:
            item_compact["members"] = members
        compact_items.append({k:v for k,v in item_compact.items() if v is not None})

    if compact_items:
        file_outline[path] = {
            "language": language,
            "items": compact_items,
        }

capabilities["ast_grep_outline"] = bool(file_outline)
capabilities["ast_grep_outline_files"] = len(file_outline)
capabilities["ast_grep_outline_items"] = top_count
capabilities["ast_grep_member_items"] = member_count

AST_LOOKUP.write_text(json.dumps({
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "symbols": {name: entries[:30] for name, entries in sorted(lookup.items())}
}, separators=(",", ":")) + "\n")

FILE_OUTLINE.write_text(json.dumps({
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "files": file_outline,
}, separators=(",", ":")) + "\n")

CAP.write_text(json.dumps(capabilities, indent=2) + "\n")
