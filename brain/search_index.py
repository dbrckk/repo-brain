#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

BRAIN = Path(".ai/brain")
OUT = BRAIN / "search-shards"

TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
STOP = {
    "the","and","for","with","from","this","that","class","return","import","package",
    "def","fun","val","var","const","public","private","protected","static","void",
    "true","false","none","null","self","int","str","string","boolean","object",
}

def load(name: str, default: Any) -> Any:
    try:
        return json.loads((BRAIN / name).read_text(encoding="utf-8"))
    except Exception:
        return default

def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")

def shard_for(token: str) -> str:
    c = token[0].lower() if token else "_"
    return c if c.isalnum() else "_"

def eligible(path: str) -> bool:
    p = path.lower()
    if p.startswith((".git/", ".ai/", "node_modules/", "vendor/", "build/", "dist/", ".gradle/")):
        return False
    return Path(path).suffix.lower() in {
        ".py",".kt",".kts",".java",".js",".jsx",".ts",".tsx",".go",".rs",".c",".cc",".cpp",
        ".h",".hpp",".cs",".rb",".php",".swift",".scala",".sh",".yaml",".yml",".toml",".json",".xml"
    }

def symbols_by_file() -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    lookup = load("lookup.json", {})
    for symbol, entries in (lookup.get("symbols") or {}).items():
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path") or entry.get("file")
            if path:
                out[path].add(symbol)
    return out

def candidate_files() -> list[str]:
    files: set[str] = set()
    idx = load("index.json", {})
    for item in idx.get("files", []) or []:
        if isinstance(item, str):
            files.add(item)
        elif isinstance(item, dict):
            path = item.get("path") or item.get("file")
            if path:
                files.add(path)
    files |= set(symbols_by_file())
    if not files:
        for p in Path(".").rglob("*"):
            if p.is_file():
                files.add(str(p).replace("\\", "/"))
    return sorted(p for p in files if eligible(p))

def main() -> None:
    by_file = symbols_by_file()
    postings: dict[str, set[str]] = defaultdict(set)
    file_tokens: dict[str, list[str]] = {}

    for path in candidate_files():
        tokens: set[str] = set()
        for symbol in by_file.get(path, set()):
            for token in TOKEN_RE.findall(symbol):
                token = token.lower()
                if token not in STOP:
                    tokens.add(token)

        p = Path(path)
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                # Bound per-file work: enough for routing, not a full search engine.
                for token in TOKEN_RE.findall(text[:400_000]):
                    token = token.lower()
                    if token not in STOP and len(token) <= 64:
                        tokens.add(token)
            except OSError:
                pass

        if tokens:
            file_tokens[path] = sorted(tokens)[:2000]
            for token in tokens:
                postings[token].add(path)

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()

    buckets: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for token, paths in postings.items():
        buckets[shard_for(token)][token] = sorted(paths)[:64]

    manifest = []
    for shard, data in sorted(buckets.items()):
        target = OUT / f"{shard}.json"
        dump(target, {"schema_version":1,"tokens":data})
        manifest.append({
            "shard": shard,
            "path": str(target),
            "token_count": len(data),
        })

    digest = hashlib.sha256()
    for path in sorted(file_tokens):
        digest.update(path.encode())
        digest.update(b"\0")
        for token in file_tokens[path]:
            digest.update(token.encode())
            digest.update(b"\0")

    dump(BRAIN / "search-manifest.json", {
        "schema_version": 1,
        "generated_by": "dbrckk/repo-brain-search-v1",
        "file_count": len(file_tokens),
        "token_count": len(postings),
        "fingerprint": digest.hexdigest(),
        "shards": manifest,
    })

if __name__ == "__main__":
    main()
