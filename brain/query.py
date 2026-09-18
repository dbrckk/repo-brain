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

def symbol(name):
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
    data = load("symbol-dependencies.json", {"symbols": {}})
    return {"symbol": name, "data": (data.get("symbols") or {}).get(name, {})}

def route():
    return load("task-route.json", {})

def session():
    return load("session-state.json", {})

def packet(name):
    return load(f"context/{name}.json", {})

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: query.py symbol <name> | references <name> | dependencies <name> | impact | tests | route | session | packet <name>")
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
