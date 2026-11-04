#!/usr/bin/env python3
"""Check a plants file before anything runs. Any model may write plants; this script decides if they are usable.

A plants file that is not valid JSON or has the wrong shape is refused with every problem listed. prove.py
calls this first, so a bad or partial answer from a model is NOT-RUN, never a crash and never PASS. Decisions
that need the tree (a file outside the repo, a stale anchor, a missing catalog form, no mode) stay with prove.py,
which reports them per plant.

Usage:
  plants_schema.py PLANTS.json [--repo DIR]     exit 0 valid, 2 refused (problems on stdout)
                                               --repo also checks every edit applies to that tree
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MODES = {"behavior": [f"M{i}" for i in range(1, 10)], "guard": [f"E{i}" for i in range(1, 16)]}
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def problems(doc: object) -> list[str]:
    """Every reason the plants file cannot be used; an empty list means valid."""
    out: list[str] = []
    if not isinstance(doc, dict):
        return ["the plants file must be a JSON object"]
    mode = doc.get("mode")
    if mode is not None and mode not in MODES:  # a missing mode is reported by prove.py's coverage check
        out.append(f"mode must be one of {sorted(MODES)}, got {mode!r}")
    plants = doc.get("plants")
    if not isinstance(plants, list) or not plants:
        return out + ["plants must be a non-empty list"]
    forms = MODES.get(mode, [])
    seen: set[str] = set()
    for n, p in enumerate(plants):
        where = f"plants[{n}]"
        if not isinstance(p, dict):
            out.append(f"{where} must be an object")
            continue
        pid = p.get("id")
        if not isinstance(pid, str) or not ID.match(pid):
            out.append(f"{where}: id must be 1 to 64 letters, digits, '_', '.' or '-'")
        elif pid in seen:
            out.append(f"{where}: duplicate id {pid}")
        else:
            seen.add(pid)
            where = f"plant {pid}"
        if forms and p.get("form") not in forms:
            out.append(f"{where}: form must be one of {forms[0]}..{forms[-1]} for mode {mode}, got {p.get('form')!r}")
        for key in ("why", "author"):
            if key in p and not isinstance(p[key], str):
                out.append(f"{where}: {key} must be a string")
        edits = p.get("edits")
        if not isinstance(edits, list) or not edits:
            out.append(f"{where}: edits must be a non-empty list")
            continue
        for k, e in enumerate(edits):
            ew = f"{where} edit {k}"
            if not isinstance(e, dict):
                out.append(f"{ew} must be an object")
                continue
            f = e.get("file")
            if not isinstance(f, str) or not f:
                out.append(f"{ew}: file must be a non-empty path string, got {f!r}")
            if "create" in e:
                if not isinstance(e["create"], str):
                    out.append(f"{ew}: create must be the new file's text")
                extra = set(e) - {"file", "create"}
                if extra:
                    out.append(f"{ew}: a create edit takes only file and create, not {sorted(extra)}")
                continue
            for key in ("old", "new"):
                if not isinstance(e.get(key), str):
                    out.append(f"{ew}: {key} must be a string")
            if isinstance(e.get("old"), str) and not e["old"] and not ("start" in e and e.get("start") == e.get("end")):
                out.append(f"{ew}: old may be empty only for an insertion at a fixed position (start == end)")
            if ("start" in e) != ("end" in e):
                out.append(f"{ew}: start and end go together")
            elif "start" in e and not (isinstance(e["start"], int) and isinstance(e["end"], int)
                                       and 0 <= e["start"] <= e["end"]):
                out.append(f"{ew}: start and end must be integers with 0 <= start <= end")
            if "file_sha256" in e and not (isinstance(e["file_sha256"], str)
                                           and re.fullmatch(r"[0-9a-f]{64}", e["file_sha256"])):
                out.append(f"{ew}: file_sha256 must be 64 lowercase hex characters")
    cov = doc.get("coverage", [])
    if not isinstance(cov, list) or not all(isinstance(c, dict) and isinstance(c.get("form"), str) for c in cov):
        out.append("coverage must be a list of {form, na} objects")
    return out


def load(path: str) -> tuple[object, list[str]]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [f"{path}: no such file"]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"{path}: not valid JSON ({exc})"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plants")
    ap.add_argument("--repo", help="also check that every edit applies to this tree as it is now")
    args = ap.parse_args(argv)
    doc, errs = load(args.plants)
    if not errs:
        errs = problems(doc)
    if not errs and args.repo:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from prove import check_plant
        errs = [f"plant {p['id']}: {why}" for p in doc["plants"] if (why := check_plant(p, Path(args.repo).resolve()))]
    for e in errs:
        print(f"plants: {e}")
    if errs:
        print(f"plants: REFUSED, {len(errs)} problem(s); nothing may run on this file")
        return 2
    print(f"plants: valid, {len(doc['plants'])} plants, mode {doc.get('mode')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
