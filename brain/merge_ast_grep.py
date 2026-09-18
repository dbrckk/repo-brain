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
IMPACT = BRAIN / "impact.json"
STATE = BRAIN / "incremental-state.json"
SYMBOL_DIR = BRAIN / "ast-symbols"
FILE_DIR = BRAIN / "file-outlines"

SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".kt", ".kts", ".gd", ".rs", ".go"
}

for legacy in (BRAIN / "outline.json", BRAIN / "ast-lookup.json", BRAIN / "file-outline.json"):
    if legacy.exists():
        legacy.unlink()

def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def symbol_shard(name: str) -> str:
    first = (name or "_")[0].lower()
    return first if first.isalnum() else "_"

def safe_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return value or "root"

def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":")) + "\n")

impact = load_json(IMPACT, {})
state = load_json(STATE, {})
mode = state.get("mode") or impact.get("index_mode") or "full"

# Load the previous committed AST shards only for incremental updates.
lookup = defaultdict(list)
file_outlines = defaultdict(dict)
if mode == "incremental":
    for shard_file in SYMBOL_DIR.glob("*.json"):
        data = load_json(shard_file, {})
        for name, entries in (data.get("symbols") or {}).items():
            lookup[name].extend(entries or [])
    for outline_file in FILE_DIR.glob("*.json"):
        data = load_json(outline_file, {})
        for path, item in (data.get("files") or {}).items():
            root = path.split("/", 1)[0] if "/" in path else "root"
            file_outlines[root][path] = item

changed = impact.get("changed_files") or []
stale_paths = {
    item.get("path") for item in changed
    if item.get("path") and Path(item["path"]).suffix.lower() in SOURCE_SUFFIXES
}

if stale_paths:
    # Remove stale file outlines.
    for root in list(file_outlines):
        for path in list(file_outlines[root]):
            if path in stale_paths:
                del file_outlines[root][path]
        if not file_outlines[root]:
            del file_outlines[root]

    # Remove stale symbol entries.
    for name in list(lookup):
        lookup[name] = [entry for entry in lookup[name] if entry.get("file") not in stale_paths]
        if not lookup[name]:
            del lookup[name]

raw_data = []
if RAW.exists() and RAW.stat().st_size:
    try:
        raw_data = json.loads(RAW.read_text())
    except Exception:
        raw_data = []
if isinstance(raw_data, dict):
    raw_data = [raw_data]
if not isinstance(raw_data, list):
    raw_data = []

top_count_new = 0
member_count_new = 0

def loc(item):
    rng = item.get("range") or {}
    start = (rng.get("start") or {}).get("line")
    end = (rng.get("end") or {}).get("line")
    return (
        (start + 1) if isinstance(start, int) else None,
        (end + 1) if isinstance(end, int) else None,
    )

for obj in raw_data:
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
        top_count_new += 1

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
            member_count_new += 1
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

# Rebuild small shards deterministically from the merged in-memory AST state.
if SYMBOL_DIR.exists():
    shutil.rmtree(SYMBOL_DIR)
if FILE_DIR.exists():
    shutil.rmtree(FILE_DIR)
SYMBOL_DIR.mkdir(parents=True, exist_ok=True)
FILE_DIR.mkdir(parents=True, exist_ok=True)

symbol_buckets = defaultdict(dict)
for name, entries in sorted(lookup.items()):
    # Dedupe identical locators after incremental merges.
    seen = set()
    clean = []
    for entry in entries:
        key = (
            entry.get("file"), entry.get("type"), entry.get("start"),
            entry.get("end"), entry.get("parent")
        )
        if key in seen:
            continue
        seen.add(key)
        clean.append(entry)
    symbol_buckets[symbol_shard(name)][name] = clean[:30]

for shard, symbols in sorted(symbol_buckets.items()):
    write_json(SYMBOL_DIR / (safe_slug(shard) + ".json"), {
        "schema_version": 2,
        "symbols": symbols,
    })

for root, files in sorted(file_outlines.items()):
    write_json(FILE_DIR / (safe_slug(root) + ".json"), {
        "schema_version": 2,
        "root": root,
        "files": files,
    })

# Artifacts do not preserve empty directories.
if not symbol_buckets:
    write_json(SYMBOL_DIR / "_.json", {"schema_version": 2, "symbols": {}})
if not file_outlines:
    write_json(FILE_DIR / "root.json", {"schema_version": 2, "root": "root", "files": {}})

total_files = sum(len(x) for x in file_outlines.values())
total_top = 0
total_members = 0
for files in file_outlines.values():
    for item in files.values():
        items = item.get("items") or []
        total_top += len(items)
        total_members += sum(len(x.get("members") or []) for x in items)

capabilities = {
    "schema_version": 4,
    "generated_by": "dbrckk/repo-brain",
    "portable_index": True,
    "ast_grep_outline": bool(file_outlines),
    "ast_index_mode": mode,
    "ast_reparsed_files": len({
        (obj.get("path") or "").removeprefix("./")
        for obj in raw_data if isinstance(obj, dict) and obj.get("path")
    }),
    "ast_grep_outline_files": total_files,
    "ast_grep_outline_items": total_top,
    "ast_grep_member_items": total_members,
    "ast_symbol_shards": len(symbol_buckets),
    "ast_file_outline_shards": len(file_outlines),
}
CAP.write_text(json.dumps(capabilities, indent=2) + "\n")

routing = {
    "schema_version": 2,
    "generated_by": "dbrckk/repo-brain",
    "available": bool(file_outlines),
    "mode": mode,
    "symbol_shard_rule": "lowercase first character; non-alphanumeric uses _.json",
    "symbol_shard_pattern": ".ai/brain/ast-symbols/<initial>.json",
    "file_outline_rule": "first path component; root-level files use root.json",
    "file_outline_pattern": ".ai/brain/file-outlines/<root>.json",
    "symbol_shards": sorted(p.name for p in SYMBOL_DIR.glob("*.json")),
    "file_outline_shards": sorted(p.name for p in FILE_DIR.glob("*.json")),
}
write_json(ROUTING, routing)

summary_path = BRAIN / "summary.md"
if summary_path.exists():
    text = summary_path.read_text().rstrip()
    text += "\n\n## ast-grep enrichment\n"
    if capabilities["ast_grep_outline"]:
        text += "- ast-grep outline: available\n"
        text += "- AST index mode: " + mode + "\n"
        text += "- AST files reparsed this run: " + str(capabilities["ast_reparsed_files"]) + "\n"
        text += "- outline files retained: " + str(total_files) + "\n"
        text += "- top-level items retained: " + str(total_top) + "\n"
        text += "- direct members retained: " + str(total_members) + "\n"
        text += "- symbol shards: " + str(len(symbol_buckets)) + "\n"
        text += "- route named symbols via ast-routing.json, then fetch one ast-symbols/<initial>.json shard\n"
    else:
        text += "- ast-grep outline: unavailable; portable index remains authoritative for routing\n"
    summary_path.write_text(text + "\n")
