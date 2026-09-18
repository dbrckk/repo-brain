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

STATE_FILE = OUT / "incremental-state.json"
SYMBOLS_FILE = OUT / "symbols.json"
IMPORTS_FILE = OUT / "imports.json"

SKIP_PARTS = {
    ".git", ".ai", ".repo-brain-tool", "node_modules", "vendor", "build", "dist",
    ".gradle", ".venv", "venv", "__pycache__", ".pytest_cache", "coverage",
    "assets", "art", "art_sources", "marketing"
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
MAX_INCREMENTAL_CHANGED = 100
MAX_INCREMENTAL_RATIO = 0.30

def git(*args, check=True):
    p = subprocess.run(["git", *args], text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or "git command failed")
    return p.stdout.strip()

def tracked_files():
    return git("ls-files").splitlines()

def valid_commit(ref):
    if not ref:
        return False
    return subprocess.run(
        ["git", "cat-file", "-e", ref + "^{commit}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

def is_ancestor(base, head):
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, head],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode == 0

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

def is_test(path):
    p = Path(path)
    lower_parts = [x.lower() for x in p.parts]
    name = p.name.lower()
    return (
        any(x in {"test", "tests", "spec", "specs", "__tests__"} for x in lower_parts[:-1])
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts", "test.kt", "test.java"))
    )

def diff_paths(base, head):
    if not base or not valid_commit(base):
        return []
    raw = git("diff", "--name-status", base, head, "--", ".", ":(exclude).ai/**", check=False)
    result = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith(("R", "C")) and len(parts) >= 3:
            result.append({"status": status, "old": parts[1], "path": parts[2]})
        elif len(parts) >= 2:
            result.append({"status": status, "path": parts[1]})
    return result

def add_symbol(symbols, path, language, kind, name, line, parent=None):
    if not name or len(symbols) >= MAX_SYMBOLS:
        return
    item = {
        "file": path, "language": language, "kind": kind,
        "name": name, "line": int(line or 1)
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
            parent = None
            add_symbol(symbols, path, "python", "function", node.name, node.lineno, parent)
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

def parse_source(path, symbols, imports):
    p = Path(path)
    language = LANG_BY_SUFFIX[p.suffix.lower()]
    try:
        text = p.read_text(errors="ignore")
    except OSError:
        return
    if language == "python":
        parse_python(path, text, symbols, imports)
    elif language in {"javascript", "typescript"}:
        for m in JS_SYMBOLS.finditer(text):
            if m.group(1):
                kind, name = "class", m.group(2)
            elif m.group(3):
                kind, name = "function", m.group(4)
            else:
                kind, name = "function", m.group(5)
            add_symbol(symbols, path, language, kind, name, text.count("\n", 0, m.start()) + 1)
        for m in JS_IMPORTS.finditer(text):
            imports[path].add(m.group(1))
    else:
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
                add_symbol(symbols, path, language, kind, name, text.count("\n", 0, m.start()) + 1)
        irx = IMPORT_RX.get(language)
        if irx:
            for m in irx.finditer(text):
                imports[path].add(m.group(1))

head = git("rev-parse", "HEAD")
all_tracked = tracked_files()
source_files = [f for f in all_tracked if allowed(f)]
source_set = set(source_files)

previous = {}
if STATE_FILE.exists():
    try:
        previous = json.loads(STATE_FILE.read_text())
    except Exception:
        previous = {}

previous_head = previous.get("indexed_head")
can_incremental = (
    valid_commit(previous_head)
    and is_ancestor(previous_head, head)
    and SYMBOLS_FILE.exists()
    and IMPORTS_FILE.exists()
)

changes = diff_paths(previous_head, head) if can_incremental else []
touched = set()
for item in changes:
    if item.get("old"):
        touched.add(item["old"])
    if item.get("path"):
        touched.add(item["path"])

too_large = (
    len(touched) > MAX_INCREMENTAL_CHANGED
    or (source_files and len(touched) / max(1, len(source_files)) > MAX_INCREMENTAL_RATIO)
)
mode = "incremental" if can_incremental and not too_large else "full"

if mode == "incremental":
    try:
        symbols = json.loads(SYMBOLS_FILE.read_text()).get("symbols", [])
        old_imports = json.loads(IMPORTS_FILE.read_text()).get("imports", {})
    except Exception:
        mode = "full"

if mode == "full":
    symbols = []
    imports = defaultdict(set)
    parse_files = source_files
    base_for_impact = "HEAD~1" if valid_commit("HEAD~1") else head
    changes = diff_paths(base_for_impact, head)
else:
    symbols = [s for s in symbols if s.get("file") not in touched and s.get("file") in source_set]
    imports = defaultdict(set)
    for path, deps in old_imports.items():
        if path not in touched and path in source_set:
            imports[path].update(deps)
    parse_files = [p for p in sorted(touched) if p in source_set and allowed(p)]
    base_for_impact = previous_head

for path in parse_files:
    parse_source(path, symbols, imports)

# Cap after merge while preserving deterministic file/name order.
symbols = sorted(
    symbols,
    key=lambda x: (x.get("file",""), int(x.get("line",1)), x.get("name",""))
)[:MAX_SYMBOLS]

languages = Counter(LANG_BY_SUFFIX[Path(f).suffix.lower()] for f in source_files)

module_to_files = defaultdict(list)
for path in source_files:
    p = Path(path)
    module_to_files[p.stem].append(path)
    if p.name == "__init__.py":
        module_to_files[p.parent.name].append(path)

edges = []
seen_edges = set()
for source, deps in sorted(imports.items()):
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
    "schema_version": 2,
    "generated_by": "dbrckk/repo-brain",
    "files_indexed": len(source_files),
    "symbol_count": len(symbols),
    "edge_count": len(edges),
    "languages": dict(languages),
    "index_mode": mode,
    "reparsed_files": len(parse_files),
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
SYMBOLS_FILE.write_text(json.dumps({"symbols": symbols}, indent=2) + "\n")
IMPORTS_FILE.write_text(json.dumps({"imports": imports_json}, indent=2) + "\n")
(OUT / "code-graph.json").write_text(json.dumps({"edges": edges}, indent=2) + "\n")

lookup = defaultdict(list)
for s in symbols:
    lookup[s["name"]].append({
        "file": s["file"], "line": s["line"],
        "kind": s["kind"], "language": s["language"]
    })
(OUT / "lookup.json").write_text(json.dumps({
    "symbols": {name: entries[:20] for name, entries in sorted(lookup.items())}
}, separators=(",", ":")) + "\n")

# Impact graph.
changed_paths = []
changed_status = {}
for item in changes:
    path = item.get("path")
    if path:
        changed_paths.append(path)
        changed_status[path] = item.get("status", "M")

changed_source = {p for p in changed_paths if p in source_set}
impacted = set(changed_source)
for edge in edges:
    if edge["target"] in changed_source:
        impacted.add(edge["source"])

# Test candidates: graph-linked tests + filename similarity.
tests = [f for f in source_files if is_test(f)]
selected_tests = set()
for test in tests:
    if test in impacted:
        selected_tests.add(test)

changed_stems = {Path(p).stem.removeprefix("test_").removesuffix("_test") for p in changed_source}
for test in tests:
    tstem = Path(test).stem.removeprefix("test_").removesuffix("_test")
    if any(stem and (stem == tstem or stem in tstem or tstem in stem) for stem in changed_stems):
        selected_tests.add(test)

impacted_symbols = [
    {"name": s["name"], "kind": s["kind"], "file": s["file"], "line": s["line"]}
    for s in symbols if s["file"] in impacted
][:300]

impact = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "base": base_for_impact,
    "head": head,
    "index_mode": mode,
    "changed_files": [{"path": p, "status": changed_status.get(p, "M")} for p in changed_paths[:200]],
    "changed_source_files": sorted(changed_source),
    "impacted_files": sorted(impacted)[:300],
    "impacted_symbols": impacted_symbols,
    "selected_tests": sorted(selected_tests)[:100],
}
(OUT / "impact.json").write_text(json.dumps(impact, indent=2) + "\n")

commands = []
selected_sorted = sorted(selected_tests)
py_tests = [x for x in selected_sorted if x.endswith(".py")]
gradle_tests = [x for x in selected_sorted if x.endswith((".kt",".java"))]
js_tests = [x for x in selected_sorted if x.endswith((".js",".jsx",".ts",".tsx"))]

if py_tests:
    commands.append({
        "command": "python -m pytest " + " ".join(py_tests[:25]),
        "purpose": "targeted tests",
        "confidence": "high" if len(py_tests) <= 10 else "medium",
        "files": py_tests[:25],
    })
if gradle_tests:
    commands.append({
        "command": "./gradlew test",
        "purpose": "targeted area fallback",
        "confidence": "medium",
        "files": gradle_tests[:25],
        "note": "Exact Gradle test filters are project-specific; inspect these test files first."
    })
if js_tests:
    commands.append({
        "command": "npm test -- " + " ".join(js_tests[:25]),
        "purpose": "targeted tests",
        "confidence": "medium",
        "files": js_tests[:25],
        "note": "Runner syntax may differ; verify package.json before execution."
    })

selection = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "selected_test_files": selected_sorted[:100],
    "commands": commands,
    "fallback": "Use .ai/commands.json or the repository's canonical full validation when no targeted test is selected.",
}
(OUT / "selected-tests.json").write_text(json.dumps(selection, indent=2) + "\n")

state = {
    "schema_version": 1,
    "generated_by": "dbrckk/repo-brain",
    "indexed_head": head,
    "base_head": base_for_impact,
    "mode": mode,
    "total_source_files": len(source_files),
    "changed_path_count": len(touched) if mode == "incremental" else len(changed_paths),
    "reparsed_files": len(parse_files),
}
STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")

summary = [
    "# Repo Brain",
    "",
    "- Index mode: " + mode,
    "- Files indexed: " + str(len(source_files)),
    "- Files reparsed this run: " + str(len(parse_files)),
    "- Symbols: " + str(len(symbols)),
    "- Internal import edges: " + str(len(edges)),
    "- Impacted files: " + str(len(impacted)),
    "- Selected tests: " + str(len(selected_tests)),
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
    "- Read impact.json first after project/change context.",
    "- Use selected-tests.json before broad validation.",
    "- Search lookup.json for symbol routing; ast-grep enrichment may provide exact ranges.",
    "- Verify source before editing.",
    "",
]
(OUT / "summary.md").write_text("\n".join(summary))
