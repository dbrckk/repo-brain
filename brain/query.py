#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

BRAIN = Path(".ai/brain")
AI = Path(".ai")

def load(path, default):
    try:
        base = AI if str(path).startswith("session-") else BRAIN
        return json.loads((base / path).read_text())
    except Exception:
        return default

def semantic_symbol(name):
    data = load("semantic-index.json", {"available": False, "symbols": {}})
    if data.get("available"):
        direct = (data.get("symbols") or {}).get(name)
        if direct:
            return {"source": "scip", "symbol": name, "data": direct}
        # SCIP symbols are fully-qualified; allow suffix/name matching as a compact fallback.
        matches = {}
        needle = name.lower()
        for key, value in (data.get("symbols") or {}).items():
            if needle in key.lower():
                matches[key] = value
                if len(matches) >= 20:
                    break
        if matches:
            return {"source": "scip", "symbol": name, "matches": matches}
    return None

def symbol(name):
    precise = semantic_symbol(name)
    if precise:
        return precise
    caps = load("capabilities.json", {})
    if caps.get("ast_grep_outline"):
        shard = name[0].lower() if name and name[0].isalnum() else "_"
        data = load(f"ast-symbols/{shard}.json", {"symbols": {}})
        entries = (data.get("symbols") or {}).get(name)
        if entries:
            return {"source":"ast-grep","symbol":name,"matches":entries}
    data = load("lookup.json", {"symbols": {}})
    return {"source":"portable","symbol":name,"matches":(data.get("symbols") or {}).get(name, [])}

def impact():
    return load("impact.json", {})

def tests():
    return load("selected-tests.json", {})

def references(name):
    data = load("references.json", {"symbols": {}})
    return {"symbol": name, "data": (data.get("symbols") or {}).get(name, {})}

def dependencies(name):
    precise = semantic_symbol(name)
    if precise:
        return precise
    data = load("symbol-dependencies.json", {"symbols": {}})
    return {"symbol": name, "data": (data.get("symbols") or {}).get(name, {})}

def search_token(token):
    token = token.lower()
    shard = token[0] if token and token[0].isalnum() else "_"
    data = load(f"search-shards/{shard}.json", {"tokens": {}})
    return {"token": token, "files": (data.get("tokens") or {}).get(token, [])}

def validation_status():
    data = load("validation-memory.json", {})
    records = data.get("records") or []
    return {
        "record_count": len(records),
        "term_count": len(data.get("term_test_scores") or {}),
        "passed": sum(1 for r in records if r.get("status") == "passed"),
        "failed": sum(1 for r in records if r.get("status") == "failed"),
        "skipped": sum(1 for r in records if r.get("status") == "skipped"),
    }

def learning_status():
    data = load("routing-learning.json", {})
    return {
        "example_count": len(data.get("examples") or []),
        "term_count": len(data.get("term_file_scores") or {}),
        "test_term_count": len(data.get("term_test_scores") or {}),
    }

def semantic_status():
    plan = load("semantic-plan.json", {})
    index = load("semantic-index.json", {})
    return {
        "plan": plan,
        "available": bool(index.get("available")),
        "document_count": index.get("document_count", 0),
        "symbol_count": index.get("symbol_count", 0),
    }

def route():
    return load("task-route.json", {})

def session():
    return load("session-state.json", {})

def packet(name):
    return load(f"context/{name}.json", {})

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: query.py symbol <name> | references <name> | dependencies <name> | search <token> | semantic-status | learning-status | validation-status | impact | tests | route | session | packet <name>")
    cmd = sys.argv[1]
    if cmd == "symbol":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: query.py symbol <name>")
        result = symbol(sys.argv[2])
    elif cmd == "references":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: query.py references <name>")
        result = references(sys.argv[2])
    elif cmd == "dependencies":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: query.py dependencies <name>")
        result = dependencies(sys.argv[2])
    elif cmd == "search":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: query.py search <token>")
        result = search_token(sys.argv[2])
    elif cmd == "validation-status":
        result = validation_status()
    elif cmd == "learning-status":
        result = learning_status()
    elif cmd == "semantic-status":
        result = semantic_status()
    elif cmd == "impact":
        result = impact()
    elif cmd == "tests":
        result = tests()
    elif cmd == "route":
        result = route()
    elif cmd == "session":
        result = session()
    elif cmd == "packet":
        if len(sys.argv) < 3:
            raise SystemExit("Usage: query.py packet <name>")
        result = packet(sys.argv[2])
    else:
        raise SystemExit("Unknown query: " + cmd)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
