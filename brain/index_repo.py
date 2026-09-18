#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(".ai/brain")
OUT.mkdir(parents=True, exist_ok=True)

SKIP_PARTS = {
    ".git", ".ai", "node_modules", "vendor", "build", "dist", ".gradle",
    ".venv", "venv", "__pycache__", ".pytest_cache", "coverage", "assets",
    "art", "art_sources", "marketing"
}
LANG_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".gd": "gdscript", ".rs": "rust", ".go": "go",
}
MAX_FILE_BYTES = 400_000
MAX_SYMBOLS = 12000
MAX_EDGES = 20000

def tracked_files():
    return subprocess.check_output(["git", "ls-files"], text=True).splitlines()

def allowed(path):
    p = Path(path)
    if any(part in SKIP_PARTS for part in p.parts):
        return False
    if p.suffix.lower() not in LANG_BY_SUFFIX:
        return False
    try:
        return p.stat().st_size <= MAX_FILE_BYTES
    except OSError:
        return False

def add_symbol(symbols, path, language, kind, name, line, parent=None):
    if not name or len(symbols) >= MAX_SYMBOLS:
        return
    item = {
        "file": path,
        "language": language,
        "kind": kind,
        "name": name,
        "line": int(line or 1),
    }
    if parent:
        item["parent"] = parent
    symbols.append(item)

def parse_python(path, text, symbols, imports):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add_symbol(symbols, path, "python", "function", node.name, node.lineno)
        elif isinstance(node, ast.ClassDef):
            add_symbol(symbols, path, "python", "class", node.name, node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports[path].add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports[path].add(node.module)

JS_SYMBOLS = re.compile(
    r"(?m)^\s*(?:export\s+)?(?:default\s+)?"
    r"(?:(class)\s+([A-Za-z_$][\w$]*)|"
    r"(?:async\s+)?(function)\s+([A-Za-z_$][\w$]*)|"
    r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^\n]*?\)\s*=>)"
)
JS_IMPORTS = re.compile(r"(?:from\s+|require\(|import\s*\()\s*['\"]([^'\"]+)['\"]")

def parse_js_like(path, language, text, symbols, imports):
    for m in JS_SYMBOLS.finditer(text):
        if m.group(1):
            kind, name = "class", m.group(2)
        elif m.group(3):
            kind, name = "function", m.group(4)
        else:
            kind, name = "function", m.group(5)
        line = text.count("\n", 0, m.start()) + 1
        add_symbol(symbols, path, language, kind, name, line)
    for m in JS_IMPORTS.finditer(text):
        imports[path].add(m.group(1))

DECL = {
    "java": re.compile(r"(?m)^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*(class|interface|enum|record)\s+([A-Za-z_$][\w$]*)|^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)+[\w<>,.?\[\] ]+\s+([A-Za-z_$][\w$]*)\s*\("),
    "kotlin": re.compile(r"(?m)^\s*(?:(?:public|private|protected|internal|open|abstract|data|sealed)\s+)*(class|interface|object|enum\s+class)\s+([A-Za-z_][\w]*)|^\s*(?:(?:public|private|protected|internal|suspend|inline|override|open)\s+)*fun\s+([A-Za-z_][\w]*)\s*\("),
    "gdscript": re.compile(r"(?m)^\s*(class_name)\s+([A-Za-z_][\w]*)|^\s*(func)\s+([A-Za-z_][\w]*)\s*\("),
    "rust": re.compile(r"(?m)^\s*(?:pub\s+)?(struct|enum|trait|fn)\s+([A-Za-z_][\w]*)"),
    "go": re.compile(r"(?m)^\s*(type)\s+([A-Za-z_][\w]*)\s+(?:struct|interface)|^\s*(func)\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)\s*\("),
}
IMPORT_RX = {
    "java": re.compile(r"(?m)^\s*import\s+(?:static\s+)?([A-Za-z0-9_.*]+)"),
    "kotlin": re.compile(r"(?m)^\s*import\s+([A-Za-z0-9_.*]+)"),
    "gdscript": re.compile(r"(?m)^\s*(?:const|var)\s+\w+\s*=\s*preload\(['\"]([^'\"]+)['\"]\)"),
    "rust": re.compile(r"(?m)^\s*use\s+([^;]+);"),
    "go": re.compile(r'(?m)^\s*import\s+(?:\w+\s+)?"([^"]+)"'),
}

def parse_regex_language(path, language, text, symbols, imports):
    rx = DECL.get(language)
    if rx:
        for m in rx.finditer(text):
            groups = [g for g in m.groups() if g]
            if not groups:
                continue
            name = groups[-1]
            kind = groups[-2] if len(groups) >= 2 else "symbol"
            if kind in {"func", "fn"}:
                kind = "function"
            elif "class" in kind or kind in {"struct", "object", "type"}:
                kind = "class"
            line = text.count("\n", 0, m.start()) + 1
            add_symbol(symbols, path, language, kind, name, line)
    irx = IMPORT_RX.get(language)
    if irx:
        for m in irx.finditer(text):
            imports[path].add(m.group(1))

files = [f for f in tracked_files() if allowed(f)]
symbols = []
imports = defaultdict(set)
languages = Counter()

for path in files:
    p = Path(path)
    language = LANG_BY_SUFFIX[p.suffix.lower()]
    languages[language] += 1
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        continue

    if language == "python":
        parse_python(path, text, symbols, imports)
    elif language in {"javascript", "typescript"}:
        parse_js_like(path, language, text, symbols, imports)
    else:
        parse_regex_language(path, language, text, symbols, imports)

module_to_files = defaultdict(list)
for path in files:
    p = Path(path)
    module_to_files[p.stem].append(path)
    if p.name == "__init__.py":
        module_to_files[p.parent.name].append(path)

edges = []
seen_edges = set()
for source, deps in imports.items():
    for dep in sorted(deps):
        root = dep.split(".")[0].split("/")[0]
        for target in module_to_files.get(root, [])[:4]:
            if source == target:
                continue
            edge = (source, target, "imports")
            if edge not in seen_edges and len(edges) < MAX_EDGES:
                seen_edges.add(edge)
                edges.append({"source": source, "target": target, "type": "imports"})

symbols_by_file = Counter(s["file"] for s in symbols)
index = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "files_indexed": len(files),
    "symbol_count": len(symbols),
    "edge_count": len(edges),
    "languages": dict(languages),
    "top_symbol_files": [
        {"file": f, "symbols": n}
        for f, n in symbols_by_file.most_common(50)
    ],
}
imports_json = {
    path: sorted(values)
    for path, values in sorted(imports.items())
    if values
}

(OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
(OUT / "symbols.json").write_text(json.dumps({"symbols": symbols}, indent=2) + "\n")
(OUT / "imports.json").write_text(json.dumps({"imports": imports_json}, indent=2) + "\n")
(OUT / "code-graph.json").write_text(json.dumps({"edges": edges}, indent=2) + "\n")

summary = [
    "# Repo Brain",
    "",
    "- Files indexed: " + str(len(files)),
    "- Symbols: " + str(len(symbols)),
    "- Internal import edges: " + str(len(edges)),
    "",
    "## Languages",
]
for lang, count in languages.most_common():
    summary.append("- " + lang + ": " + str(count) + " files")

summary += ["", "## Highest-density symbol files"]
for file, count in symbols_by_file.most_common(20):
    summary.append("- " + file + ": " + str(count) + " symbols")

summary += [
    "",
    "## Agent routing",
    "- Search symbols.json by symbol name before opening broad source files.",
    "- Use code-graph.json to inspect likely internal import relationships.",
    "- Use imports.json when a changed file crosses module boundaries.",
    "- Treat graph edges as static hints; verify source before editing.",
    "",
]
(OUT / "summary.md").write_text("\n".join(summary))
