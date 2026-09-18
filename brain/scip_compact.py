#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
RAW = BRAIN / "scip.raw.json"

def dump(name: str, value: Any) -> None:
    (BRAIN / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def role_names(value: int) -> list[str]:
    # SCIP SymbolRole bit flags: Definition=1, Import=2, WriteAccess=4, ReadAccess=8,
    # Generated=16, Test=32, ForwardDefinition=64.
    flags = [
        (1, "definition"), (2, "import"), (4, "write"), (8, "read"),
        (16, "generated"), (32, "test"), (64, "forward-definition"),
    ]
    return [name for bit, name in flags if value & bit]

def main() -> None:
    if not RAW.is_file():
        dump("semantic-index.json", {
            "schema_version": 1,
            "generated_by": "dbrckk/repo-brain-semantic",
            "available": False,
            "reason": "No SCIP JSON input. Run dedicated semantic refresh to create it.",
            "symbols": {},
            "files": {},
        })
        return

    try:
        data = json.loads(RAW.read_text(encoding="utf-8"))
    except Exception as exc:
        dump("semantic-index.json", {
            "schema_version": 1,
            "generated_by": "dbrckk/repo-brain-semantic",
            "available": False,
            "reason": f"Invalid SCIP JSON: {exc}",
            "symbols": {},
            "files": {},
        })
        return

    symbols: dict[str, dict[str, Any]] = {}
    files: dict[str, dict[str, Any]] = {}
    refs: dict[str, set[str]] = defaultdict(set)

    for doc in data.get("documents", []) or []:
        path = doc.get("relativePath") or doc.get("relative_path") or ""
        if not path:
            continue
        fdefs, frefs = [], []
        for occ in doc.get("occurrences", []) or []:
            symbol = occ.get("symbol") or ""
            if not symbol:
                continue
            roles_value = occ.get("symbolRoles", occ.get("symbol_roles", 0)) or 0
            roles = role_names(int(roles_value))
            rng = occ.get("range") or []
            entry = {"file": path, "range": rng, "roles": roles}
            item = symbols.setdefault(symbol, {"definitions": [], "references": []})
            if "definition" in roles:
                item["definitions"].append(entry)
                fdefs.append(symbol)
            else:
                item["references"].append(entry)
                refs[symbol].add(path)
                frefs.append(symbol)

        files[path] = {
            "definitions": sorted(set(fdefs))[:200],
            "references": sorted(set(frefs))[:400],
        }

    for symbol, item in symbols.items():
        item["reference_files"] = sorted(refs.get(symbol, set()))
        item["definition_count"] = len(item["definitions"])
        item["reference_count"] = len(item["references"])
        # Keep the committed routing index bounded.
        item["definitions"] = item["definitions"][:32]
        item["references"] = item["references"][:128]

    dump("semantic-index.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-semantic",
        "available": True,
        "document_count": len(files),
        "symbol_count": len(symbols),
        "symbols": symbols,
        "files": files,
    })

if __name__ == "__main__":
    main()
