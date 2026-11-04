#!/usr/bin/env python3
"""Write a plant list: small deliberate bugs in the code under test.

Reads ONLY the source files it is given, never the tests, so the plants are not
chosen to fit the tests (author != grader). Each plant records the sha256 of the
file it was cut from; prove.py refuses a plant whose file has changed since.

Usage:
  plant.py --repo DIR --out plants.json FILE [FILE ...]
           [--lines FILE:START-END ...] [--max N] [--seed S]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import sys
from pathlib import Path

COMPARE_SWAP = {">=": ">", ">": ">=", "<=": "<", "<": "<=", "==": "!=", "!=": "==",
                "is not": "is", "is": "is not", "not in": "in", "in": "not in"}
BINOP_SWAP = {"+": "-", "-": "+", "*": "/", "/": "*", "//": "*", "%": "*"}
BOOL_SWAP = {"and": "or", "or": "and"}
SKIP_MARK = "pragma: no plant"
FORM_OF = {"compare": "M1", "arith": "M2", "bool": "M3", "constant": "M4", "drop-not": "M5",
           "return-none": "M6", "negate-if": "M7", "drop-call": "M8", "reraise": "M9"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def line_offsets(text: str) -> list[int]:
    offs, pos = [0], 0
    for line in text.splitlines(keepends=True):
        pos += len(line)
        offs.append(pos)
    return offs


class PyPlanter:
    """Plants for one Python file, as exact text edits at AST positions."""

    def __init__(self, rel: str, text: str):
        self.rel, self.text = rel, text
        self.offs = line_offsets(text)
        self.lines = text.splitlines()
        self.plants: list[dict] = []

    def pos(self, lineno: int, col: int) -> int:
        # ast columns are UTF-8 byte offsets; convert within the line
        line = self.lines[lineno - 1] if lineno - 1 < len(self.lines) else ""
        return self.offs[lineno - 1] + len(line.encode()[:col].decode(errors="ignore"))

    def span(self, node: ast.AST) -> tuple[int, int]:
        return (self.pos(node.lineno, node.col_offset),
                self.pos(node.end_lineno, node.end_col_offset))

    def add(self, start: int, end: int, new: str, kind: str, lineno: int) -> None:
        if SKIP_MARK in (self.lines[lineno - 1] if lineno - 1 < len(self.lines) else ""):
            return
        old = self.text[start:end]
        if old == new:
            return
        mutated = self.text[:start] + new + self.text[end:]
        try:
            ast.parse(mutated)
        except SyntaxError:
            return
        self.plants.append({"file": self.rel, "line": lineno, "kind": kind,
                            "start": start, "end": end, "old": old, "new": new})

    def op_between(self, left: ast.AST, right: ast.AST, table: dict, kind: str) -> None:
        a = self.pos(left.end_lineno, left.end_col_offset)
        b = self.pos(right.lineno, right.col_offset)
        gap = self.text[a:b]
        for op in sorted(table, key=len, reverse=True):
            m = re.search(r"(?<![\w=!<>])" + re.escape(op).replace(r"\ ", r"\s+") + r"(?![\w=])", gap)
            if m and gap[:m.start()].strip(" \t\n\\(") == "" and gap[m.end():].strip(" \t\n\\)") == "":
                self.add(a + m.start(), a + m.end(), table[op], kind, left.end_lineno)
                return

    def run(self) -> list[dict]:
        tree = ast.parse(self.text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and len(node.ops) == 1:
                self.op_between(node.left, node.comparators[0], COMPARE_SWAP, "compare")
            elif isinstance(node, ast.BinOp):
                self.op_between(node.left, node.right, BINOP_SWAP, "arith")
            elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
                self.op_between(node.values[0], node.values[1], BOOL_SWAP, "bool")
            elif isinstance(node, ast.Constant) and hasattr(node, "end_col_offset"):
                s, e = self.span(node)
                if isinstance(node.value, bool):
                    self.add(s, e, str(not node.value), "constant", node.lineno)
                elif isinstance(node.value, int):
                    self.add(s, e, str(node.value + 1), "constant", node.lineno)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                s, e = self.span(node)
                inner = self.text[slice(*self.span(node.operand))]
                self.add(s, e, f"({inner})", "drop-not", node.lineno)
            elif isinstance(node, ast.Return) and node.value is not None and not (
                    isinstance(node.value, ast.Constant) and node.value.value is None):
                s, e = self.span(node.value)
                self.add(s, e, "None", "return-none", node.lineno)
            elif isinstance(node, ast.If):
                s, e = self.span(node.test)
                self.add(s, e, f"not ({self.text[s:e]})", "negate-if", node.lineno)
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                s, e = self.span(node)
                self.add(s, e, "pass", "drop-call", node.lineno)
            elif isinstance(node, ast.ExceptHandler) and node.body:
                first = node.body[0]
                s, _ = self.span(first)
                indent = " " * first.col_offset
                self.add(s, s, f"raise\n{indent}", "reraise", first.lineno)
        return self.plants


JS_RULES = [  # (kind, pattern, replacement); applied to code outside strings and comments
    ("compare", r"===", "!=="), ("compare", r"!==", "==="),
    ("compare", r"(?<![=!<>])>=(?!=)", ">"), ("compare", r"(?<![=!<>])<=(?!=)", "<"),
    ("compare", r"(?<![=!<>\-])>(?![=>])", ">="), ("compare", r"(?<![=!<])<(?![=<])", "<="),
    ("bool", r"&&", "||"), ("bool", r"\|\|", "&&"),
    ("constant", r"\btrue\b", "false"), ("constant", r"\bfalse\b", "true"),
    ("return-none", r"\breturn\s+(?!;)[^;\n]+", "return undefined"),
]
JS_STRING = re.compile(r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/)""", re.S)


def js_plants(rel: str, text: str) -> list[dict]:
    masked = JS_STRING.sub(lambda m: " " * len(m.group(0)), text)
    offs = line_offsets(text)
    out = []
    for kind, pat, new in JS_RULES:
        for m in re.finditer(pat, masked):
            lineno = next(i for i in range(1, len(offs)) if offs[i] > m.start())
            if SKIP_MARK in text.splitlines()[lineno - 1]:
                continue
            out.append({"file": rel, "line": lineno, "kind": kind, "start": m.start(),
                        "end": m.end(), "old": text[m.start():m.end()], "new": new})
    return out


def parse_ranges(specs: list[str]) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    for spec in specs:
        path, _, rng = spec.rpartition(":")
        a, _, b = rng.partition("-")
        ranges.setdefault(path, []).append((int(a), int(b or a)))
    return ranges


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="repository root (required: never defaults to cwd)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lines", nargs="*", default=[], help="only plant on these lines, FILE:START-END")
    ap.add_argument("--max", type=int, default=0, help="keep a seeded random sample of at most N plants")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("files", nargs="+")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    ranges = parse_ranges(args.lines)
    plants: list[dict] = []
    for f in args.files:
        path = (repo / f).resolve()
        if repo not in path.parents:
            print(f"plant: {f} is outside the repo", file=sys.stderr)
            return 2
        rel = str(path.relative_to(repo))
        if not path.is_file():
            print(f"plant: {rel} does not exist", file=sys.stderr)
            return 2
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            print(f"plant: {rel} is not UTF-8 text; write its plants by hand", file=sys.stderr)
            continue
        if path.suffix == ".py":
            try:
                found = PyPlanter(rel, text).run()
            except SyntaxError as exc:
                print(f"plant: {rel} does not parse ({exc.msg}, line {exc.lineno}); skipped", file=sys.stderr)
                continue
        elif path.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            found = js_plants(rel, text)
        else:
            print(f"plant: no planter for {rel}; write its plants by hand (see SKILL.md)", file=sys.stderr)
            continue
        if rel in ranges:
            found = [p for p in found if any(a <= p["line"] <= b for a, b in ranges[rel])]
        for p in found:
            p["file_sha256"] = sha256(data)
        plants.extend(found)

    order = lambda p: (p["file"], p["start"], p["kind"], p["new"])  # noqa: E731
    plants.sort(key=order)
    present = {FORM_OF[p["kind"]] for p in plants}
    if args.max and len(plants) > args.max:
        # keep one plant of every form the code has first, so a sample never hides a form behind "n/a"
        rng = random.Random(args.seed)
        keep: list[dict] = []
        for form in sorted(present, key=lambda f: int(f[1:])):
            keep.append(rng.choice([p for p in plants if FORM_OF[p["kind"]] == form]))
        rest = [p for p in plants if p not in keep]
        keep += rng.sample(rest, max(0, args.max - len(keep)))
        plants = sorted(keep, key=order)
    out = []
    for i, p in enumerate(plants, 1):
        out.append({"id": f"M{i:04d}", "form": FORM_OF[p["kind"]], "author": "plant.py",
                    "why": f"{p['kind']} at {p['file']}:{p['line']}: {p['old']!r} -> {p['new']!r}",
                    "edits": [{k: p[k] for k in ("file", "file_sha256", "start", "end", "old", "new")}]})
    seen = {p["form"] for p in out}
    # n/a only for forms the code really does not have; a form present but not planted stays uncovered
    coverage = [{"form": f, "na": "no such code site in the planted lines"}
                for f in FORM_OF.values() if f not in seen and f not in present]
    doc = {"version": 1, "mode": "behavior", "plants": out, "coverage": sorted(
        {c["form"]: c for c in coverage}.values(), key=lambda c: int(c["form"][1:]))}
    doc["plants_sha256"] = sha256(json.dumps(out, sort_keys=True).encode())
    Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")
    kinds: dict[str, int] = {}
    for p in plants:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"plant: {len(out)} plants in {len(args.files)} files -> {args.out} "
          f"({', '.join(f'{k} {v}' for k, v in sorted(kinds.items()))})")
    return 0 if out else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
