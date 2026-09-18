#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

BRAIN = Path(".ai/brain")
RAW = BRAIN / "ast-grep-outline.raw.json"
CAP = BRAIN / "capabilities.json"
ROUTING = BRAIN / "ast-routing.json"
SYMBOL_DIR = BRAIN / "ast-symbols"
FILE_DIR = BRAIN / "file-outlines"

for legacy in (BRAIN / "outline.json", BRAIN / "ast-lookup.json", BRAIN / "file-outline.json"):
    if legacy.exists():
        legacy.unlink()
for directory in (SYMBOL_DIR, FILE_DIR):
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)

capabilities = {
    "schema_version": 3,
    "generated_by": "dbrckk/repo-brain",
    "portable_index": True,
    "ast_grep_outline": False,
    "ast_grep_outline_files": 0,
    "ast_grep_outline_items": 0,
    "ast_grep_member_items": 0,
    "ast_symbol_shards": 0,
    "ast_file_outline_shards": 0,
}

def symbol_shard(name: str) -> str:
    first = (name or "_")[0].lower()
    return first if first.isalnum() else "_"

def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return value or "root"

def write_json(path: Path, value):
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")

def write_empty():
    write_json(ROUTING, {
        "schema_version": 1,
        "available": False,
        "symbol_shard_pattern": ".ai/brain/ast-symbols/<initial>.json",
        "file_outline_pattern": ".ai/brain/file-outlines/<root>.json",
    })
    write_json(SYMBOL_DIR / "_.json", {"symbols": {}})
    write_json(FILE_DIR / "root.json", {"files": {}})
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
file_outlines = defaultdict(dict)
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

        base = {"file": path, "type": typ, "start": start, "end": end}
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
            member_name = member["name"]
            m = {
                "name": member_name,
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
            lookup[member_name].append({k:v for k,v in ment.items() if v is not None})

        compact = {"name": name, "type": typ, "start": start, "end": end}
        if members:
            compact["members"] = members
        compact_items.append({k:v for k,v in compact.items() if v is not None})

    if compact_items:
        root = path.split("/", 1)[0] if "/" in path else "root"
        file_outlines[root][path] = {
            "language": language,
            "items": compact_items,
        }

symbol_buckets = defaultdict(dict)
for name, entries in sorted(lookup.items()):
    symbol_buckets[symbol_shard(name)][name] = entries[:30]

for shard, symbols in sorted(symbol_buckets.items()):
    write_json(SYMBOL_DIR / (safe_slug(shard) + ".json"), {
        "schema_version": 1,
        "symbols": symbols,
    })

for root, files in sorted(file_outlines.items()):
    write_json(FILE_DIR / (safe_slug(root) + ".json"), {
        "schema_version": 1,
        "root": root,
        "files": files,
    })

capabilities["ast_grep_outline"] = bool(file_outlines)
capabilities["ast_grep_outline_files"] = sum(len(x) for x in file_outlines.values())
capabilities["ast_grep_outline_items"] = top_count
capabilities["ast_grep_member_items"] = member_count
capabilities["ast_symbol_shards"] = len(symbol_buckets)
capabilities["ast_file_outline_shards"] = len(file_outlines)

routing = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "available": bool(file_outlines),
    "symbol_shard_rule": "lowercase first character; non-alphanumeric uses _.json",
    "symbol_shard_pattern": ".ai/brain/ast-symbols/<initial>.json",
    "file_outline_rule": "first path component; root-level files use root.json",
    "file_outline_pattern": ".ai/brain/file-outlines/<root>.json",
    "symbol_shards": sorted(p.name for p in SYMBOL_DIR.glob("*.json")),
    "file_outline_shards": sorted(p.name for p in FILE_DIR.glob("*.json")),
}
write_json(ROUTING, routing)
CAP.write_text(json.dumps(capabilities, indent=2) + "\n")

summary_path = BRAIN / "summary.md"
if summary_path.exists():
    text = summary_path.read_text().rstrip()
    text += "\n\n## ast-grep enrichment\n"
    if capabilities["ast_grep_outline"]:
        text += "- ast-grep outline: available\n"
        text += "- outline files: " + str(capabilities["ast_grep_outline_files"]) + "\n"
        text += "- top-level items: " + str(capabilities["ast_grep_outline_items"]) + "\n"
        text += "- direct members: " + str(capabilities["ast_grep_member_items"]) + "\n"
        text += "- symbol shards: " + str(capabilities["ast_symbol_shards"]) + "\n"
        text += "- route named symbols via ast-routing.json, then fetch one ast-symbols/<initial>.json shard\n"
    else:
        text += "- ast-grep outline: unavailable; portable index remains authoritative for routing\n"
    summary_path.write_text(text + "\n")
