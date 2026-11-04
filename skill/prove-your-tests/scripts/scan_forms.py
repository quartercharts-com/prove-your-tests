#!/usr/bin/env python3
"""List every real way the code reaches a guarded name, before anyone writes a plant.

The house style is where escapes hide: a plant writer copies the forms the repo
already uses (aliases, getattr, stored callables, raw HTTP or SQL, async twins,
flags) before inventing new ones. Test files are skipped by default, so the
plant writer never sees the tests through this scan.

Usage:
  scan_forms.py --repo DIR --name charge [--name LEDGER ...] [--include-tests] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rb", ".java", ".kt", ".php", ".cs"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".tox", "vendor"}
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__|spec|specs)(/|$)|(^|/)test_[^/]*$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$")

# (form id, label, regex with {n} for the escaped name)
FORMS = [
    ("E1", "alias import", r"import\s+[^\n]*\b{n}\b\s+as\s+\w+|\{{[^}}]*\b{n}\b\s*(as|:)\s*\w+"),
    ("E2", "module attribute", r"\b\w+\.{n}\b"),
    ("E3", "getattr or string dispatch", r"getattr\([^)]*['\"]{n}['\"]|\[['\"]{n}['\"]\]|['\"]{n}['\"]\s*:"),
    ("E4", "keyword or default argument", r"\b{n}\s*=[^=]|\*\*\w+"),
    ("E5", "stored callable", r"=\s*[\w.]*\b{n}\b\s*(,|\]|\}}|\)|$)|lambda[^:]*:\s*[\w.]*\b{n}\b|partial\([\w.]*\b{n}\b"),
    ("E6", "subclass, override or wrapper", r"class\s+\w+\([^)]*\)|def\s+{n}\s*\(|@\w+"),
    ("E7", "raw transport (HTTP, SQL, shell)", r"\b(requests|httpx|urllib|fetch|axios|aiohttp)\b|\b(INSERT|UPDATE|DELETE)\s+(INTO\s+)?\w+|subprocess|os\.system|execute\("),
    ("E8", "async or thread twin", r"\basync\s+def\b|\bawait\b|to_thread|Thread\(|create_task|Promise\.|setTimeout"),
    ("E9", "second writer or reader", r"\b{n}\b"),
    ("E10", "house constants, enums, settings", r"\b[A-Z][A-Z0-9_]{{2,}}\b|settings\.|config\.|Enum\b"),
    ("E13", "claim in a comment or docstring", r"(#|//|/\*|\"\"\"|''')[^\n]*\b(check|guard|only|never|always|validated?|safe)\b"),
    ("E14", "error path", r"\bexcept\b|\bcatch\b|\bretry\b|\bfallback\b|\bfinally\b"),
    ("E15", "config switch", r"os\.environ|getenv|process\.env|\bflag\b|feature|_ENABLED|DEBUG"),
]


def files(repo: Path, include_tests: bool):
    for p in sorted(repo.rglob("*")):
        rel = p.relative_to(repo).as_posix()
        if p.is_file() and p.suffix in CODE_EXT and not (set(p.relative_to(repo).parts) & SKIP_DIRS):
            if include_tests or not TEST_PATH.search(rel):
                yield p, rel


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--name", action="append", required=True, help="a guarded function, table, route or constant")
    ap.add_argument("--include-tests", action="store_true", help="also scan tests (never for a plant writer)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()

    hits: list[dict] = []
    for path, rel in files(repo, args.include_tests):
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        names_here = [n for n in args.name if any(n in l for l in lines)]
        if not names_here:
            continue  # only files that touch a guarded name matter; their neighbours are the escapes
        for n in names_here:
            for form, label, pat in FORMS:
                rx = re.compile(pat.format(n=re.escape(n)))
                for i, line in enumerate(lines, 1):
                    if rx.search(line) and (n in line or form in {"E7", "E8", "E10", "E13", "E14", "E15", "E6"}):
                        hits.append({"name": n, "form": form, "label": label, "file": rel, "line": i,
                                     "text": line.strip()[:160]})
    seen = set()
    hits = [h for h in hits if (k := (h["name"], h["form"], h["file"], h["line"])) not in seen and not seen.add(k)]

    if args.json:
        print(json.dumps(hits, indent=2))
        return 0
    found = {h["form"] for h in hits}
    print(f"# Real call forms for {', '.join(args.name)} ({len(hits)} sites, tests {'included' if args.include_tests else 'skipped'})\n")
    for form, label, _ in FORMS:
        rows = [h for h in hits if h["form"] == form]
        print(f"## {form} {label}: {len(rows)} sites" + ("" if rows else " (none found: still plant one, or write n/a with why)"))
        for h in rows[:25]:
            print(f"- {h['file']}:{h['line']}  `{h['text']}`")
        if len(rows) > 25:
            print(f"- ... {len(rows) - 25} more")
        print()
    print("E11 spelling and type variants, E12 every method and route form: check by hand, no text pattern finds them.")
    print(f"Forms with sites: {len(found)}/{len(FORMS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
