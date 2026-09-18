#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

BRAIN = Path(".ai/brain")
RAW = BRAIN / "ast-grep-outline.raw.json"
OUTLINE = BRAIN / "outline.json"
CAP = BRAIN / "capabilities.json"

capabilities = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "portable_index": True,
    "ast_grep_outline": False,
    "ast_grep_outline_files": 0,
    "ast_grep_outline_items": 0,
}

if not RAW.exists() or RAW.stat().st_size == 0:
    OUTLINE.write_text(json.dumps({
        "schema_version": 1,
        "available": False,
        "files": []
    }, separators=(",", ":")) + "\n")
    CAP.write_text(json.dumps(capabilities, indent=2) + "\n")
    raise SystemExit(0)

try:
    data = json.loads(RAW.read_text())
except Exception:
    OUTLINE.write_text(json.dumps({
        "schema_version": 1,
        "available": False,
        "files": []
    }, separators=(",", ":")) + "\n")
    CAP.write_text(json.dumps(capabilities, indent=2) + "\n")
    raise SystemExit(0)

if isinstance(data, dict):
    data = [data]
if not isinstance(data, list):
    data = []

def compact_entry(item):
    rng = item.get("range") or {}
    start = (rng.get("start") or {}).get("line")
    end = (rng.get("end") or {}).get("line")
    entry = {
        "name": item.get("name"),
        "type": item.get("symbolType"),
        "start": (start + 1) if isinstance(start, int) else None,
        "end": (end + 1) if isinstance(end, int) else None,
    }
    if item.get("signature"):
        entry["signature"] = item["signature"]
    if item.get("isExported") is not None:
        entry["exported"] = bool(item.get("isExported"))
    if item.get("isImport") is not None:
        entry["import"] = bool(item.get("isImport"))

    members = []
    for member in item.get("members") or []:
        mrng = member.get("range") or {}
        mstart = (mrng.get("start") or {}).get("line")
        mend = (mrng.get("end") or {}).get("line")
        m = {
            "name": member.get("name"),
            "type": member.get("symbolType"),
            "start": (mstart + 1) if isinstance(mstart, int) else None,
            "end": (mend + 1) if isinstance(mend, int) else None,
        }
        if member.get("signature"):
            m["signature"] = member["signature"]
        members.append({k:v for k,v in m.items() if v is not None})
    if members:
        entry["members"] = members
    return {k:v for k,v in entry.items() if v is not None}

files = []
item_count = 0
for obj in data:
    if not isinstance(obj, dict):
        continue
    items = [compact_entry(x) for x in (obj.get("items") or []) if isinstance(x, dict)]
    if not items:
        continue
    item_count += len(items)
    files.append({
        "path": obj.get("path"),
        "language": obj.get("language"),
        "items": items,
    })

available = bool(files)
payload = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "available": available,
    "files": files,
}
OUTLINE.write_text(json.dumps(payload, separators=(",", ":")) + "\n")

capabilities["ast_grep_outline"] = available
capabilities["ast_grep_outline_files"] = len(files)
capabilities["ast_grep_outline_items"] = item_count
CAP.write_text(json.dumps(capabilities, indent=2) + "\n")
