#!/usr/bin/env python3
"""Join shard reports of one plants file into one verdict.

PASS only when the shards together ran EXACTLY the plants in the plants file
(none missing, none extra, none twice), all on one plants file and one repo
head, and every plant passes the same rules as an unsharded run.

Usage:
  union.py --plants plants.json SHARD_OUT_DIR [SHARD_OUT_DIR ...] [--min-plants N]
Exit: 0 PASS, 1 FAIL, 2 NOT-RUN.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prove import coverage_report, plants_digest, verdict  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plants", required=True)
    ap.add_argument("--min-plants", type=int, default=25)
    ap.add_argument("shards", nargs="+")
    args = ap.parse_args(argv)

    doc = json.loads(Path(args.plants).read_text())
    digest = plants_digest(doc["plants"])
    expected = [p["id"] for p in doc["plants"]]
    reports, problems = [], []
    for d in args.shards:
        f = Path(d) / "report.json"
        if not f.exists():
            problems.append(f"{d}: no report.json")
            continue
        reports.append(json.loads(f.read_text()))
    for r in reports:
        if r["plants_sha256"] != digest:
            problems.append(f"shard {r['shard']}: ran a different plants file ({r['plants_sha256'][:12]})")
    heads = {r["git"]["head"] for r in reports}
    if len(heads) > 1:
        problems.append(f"shards ran on different repo heads: {sorted(map(str, heads))}")
    baseline = "PASSED" if reports and all(r["baseline"] == "PASSED" for r in reports) else "NOT-RUN in a shard"
    results = [x for r in reports for x in r["results"]]
    v, reasons = verdict(baseline, results, expected, args.min_plants, coverage_report(doc, doc["plants"]))
    if problems:
        reasons = problems + reasons
        v = "FAIL" if any("different" in p for p in problems) else ("FAIL" if v == "FAIL" else "NOT-RUN")
    print(f"union: {v}: {len(reports)} shards, {len(results)}/{len(expected)} plants")
    for line in reasons:
        print(f"  - {line}")
    return {"PASS": 0, "FAIL": 1}.get(v, 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
