#!/usr/bin/env python3
"""Prove a test suite catches the plants: every plant must turn the tests RED,
the file must come back byte-identical, and the tests must be GREEN again.

No model runs here; this is a plain script. It never guesses: anything it could
not run is NOT-RUN, and NOT-RUN is never PASS.

Usage:
  prove.py --repo DIR --plants plants.json --test-cmd "CMD" --out DIR
           [--timeout S] [--min-plants N] [--control each|none]
           [--baseline-runs N] [--allow-dirty] [--only ID ...] [--shard I/N]
  prove.py --recover OUT_DIR        restore files after a crash or kill

The repo must be a git work tree with nothing uncommitted (so `git status` can
always show what a crash left behind); --allow-dirty overrides that.

Exit: 0 PASS, 1 FAIL, 2 NOT-RUN or bad input, 3 a restore failed (run --recover).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plants_schema  # noqa: E402

BEHAVIOR_FORMS = [f"M{i}" for i in range(1, 10)]
GUARD_FORMS = [f"E{i}" for i in range(1, 16)]
FORMS = {"behavior": BEHAVIOR_FORMS, "guard": GUARD_FORMS}
TAIL = 2000
OUT_MARKER = ".prove-your-tests-out"  # written in every out dir, so a later run can tell reports from user work


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plants_digest(plants: list[dict]) -> str:
    return sha256(json.dumps(plants, sort_keys=True).encode())


class Interrupted(Exception):
    pass


def _raise_interrupt(signum, frame):
    raise Interrupted(f"signal {signum}")


def run_tests(cmd: str, repo: Path, timeout: float) -> tuple[str, int | None, float, str]:
    """Return (outcome, rc, seconds, output tail); outcome is PASSED, FAILED or TIMEOUT."""
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, shell=True, cwd=repo, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return "TIMEOUT", None, time.monotonic() - t0, out.decode(errors="replace")[-TAIL:]
    except BaseException:
        os.killpg(proc.pid, signal.SIGKILL)  # never leave a test run going against a planted file
        proc.wait()
        raise
    rc = proc.returncode
    return ("PASSED" if rc == 0 else "FAILED"), rc, time.monotonic() - t0, out.decode(errors="replace")[-TAIL:]


def plan_plant(plant: dict, repo: Path) -> tuple[dict[str, tuple[bool, str]], str | None]:
    """Work out every file's planted text without touching disk.

    Edits apply in order; a later edit on the same file is checked against the text the earlier ones left.
    Returns ({file: (created, text)}, None) or ({}, why the plant cannot be applied to the tree as it is now).
    """
    if not plant.get("edits"):
        return {}, "no edits"
    final: dict[str, tuple[bool, str]] = {}
    for e in plant["edits"]:
        path = (repo / e["file"]).resolve()
        if repo not in path.parents:
            return {}, f"{e['file']} is outside the repo"
        if "create" in e:
            if path.exists() or e["file"] in final:
                return {}, f"{e['file']} already exists (a create plant must make a new file)"
            final[e["file"]] = (True, e["create"])
            continue
        if e["file"] in final:
            created, text = final[e["file"]]
        else:
            if not path.is_file():
                return {}, f"{e['file']} does not exist"
            data = path.read_bytes()
            if e.get("file_sha256") and sha256(data) != e["file_sha256"]:
                return {}, f"{e['file']} changed since the plant was written (sha256 differs)"
            try:
                created, text = False, data.decode("utf-8")
            except UnicodeDecodeError:
                return {}, f"{e['file']} is not UTF-8 text; plant it by hand or skip it"
        if "start" in e:
            if text[e["start"]:e["end"]] != e["old"]:
                return {}, f"{e['file']}: text at {e['start']}:{e['end']} is not the planted 'old'"
            text = text[:e["start"]] + e["new"] + text[e["end"]:]
        elif text.count(e["old"]) != 1:
            return {}, f"{e['file']}: 'old' occurs {text.count(e['old'])} times, needs exactly 1"
        else:
            text = text.replace(e["old"], e["new"], 1)
        final[e["file"]] = (created, text)
    for rel, (created, text) in final.items():
        if not created and (repo / rel).read_bytes() == text.encode("utf-8"):
            return {}, f"{rel}: the plant changes nothing (a no-op plant cannot prove a kill)"
    return final, None


def check_plant(plant: dict, repo: Path) -> str | None:
    """Return why the plant cannot be applied to the tree as it is now, or None."""
    return plan_plant(plant, repo)[1]


def apply_plant(plant: dict, repo: Path, journal: Path) -> None:
    final, problem = plan_plant(plant, repo)
    if problem:
        raise ValueError(problem)
    saved = []
    for rel, (created, _) in final.items():
        path = repo / rel
        if created:
            saved.append({"file": rel, "created": True,
                          "made_dirs": [str(d.relative_to(repo)) for d in reversed(path.parents)
                                        if repo in d.parents and not d.exists()]})
        else:
            saved.append({"file": rel, "created": False, "bytes": base64.b64encode(path.read_bytes()).decode()})
    tmp = journal.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"plant": plant["id"], "saved": saved}))
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, journal)  # the journal is on disk before any file changes
    for rel, (created, text) in final.items():
        path = repo / rel
        if created:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))  # exact bytes: no newline or locale translation


def restore(repo: Path, journal: Path) -> bool:
    """Put every file back from the journal; True only when each is verified."""
    if not journal.exists():
        return True
    doc = json.loads(journal.read_text())
    ok = True
    for s in doc["saved"]:
        path = repo / s["file"]
        try:
            if s["created"]:
                if path.exists():
                    path.unlink()
                for d in reversed(s["made_dirs"]):
                    try:
                        (repo / d).rmdir()
                    except OSError:
                        pass
                ok &= not path.exists() and not any((repo / d).exists() for d in s["made_dirs"])
            else:
                original = base64.b64decode(s["bytes"])
                if not (path.is_file() and path.read_bytes() == original):  # an unchanged file needs no write
                    path.write_bytes(original)
                ok &= path.read_bytes() == original
        except OSError as exc:  # keep going: put back every other file, then report not restored
            print(f"prove: could not restore {s['file']}: {exc}", file=sys.stderr)
            ok = False
    if ok:
        journal.unlink()
    return ok


def coverage_report(doc: dict, plants: list[dict]) -> dict:
    mode = doc.get("mode")
    if mode not in FORMS:
        return {"mode": mode, "ok": False, "missing": [], "why": "plants file has no mode (behavior or guard)"}
    planted = {p.get("form") for p in plants}
    na = {c["form"]: c["na"] for c in doc.get("coverage", []) if c.get("na", "").strip()}
    missing = [f for f in FORMS[mode] if f not in planted and f not in na]
    return {"mode": mode, "ok": not missing, "missing": missing,
            "covered": len(FORMS[mode]) - len(missing), "total": len(FORMS[mode]),
            "planted": sorted(f for f in planted if f in FORMS[mode]), "na": na}


def verdict(baseline: str, results: list[dict], expected_ids: list[str], min_plants: int,
            coverage: dict) -> tuple[str, list[str]]:
    """PASS only when everything was run, killed, restored and controlled; FAIL beats NOT-RUN."""
    fail, notrun = [], []
    if baseline != "PASSED":
        notrun.append(f"baseline is {baseline}: the tests must be green before any plant")
    ran = [r["id"] for r in results]
    dup = sorted({i for i in ran if ran.count(i) > 1})
    if dup:
        fail.append(f"plants run twice: {dup}")
    missing = sorted(set(expected_ids) - set(ran))
    extra = sorted(set(ran) - set(expected_ids))
    if missing:
        notrun.append(f"{len(missing)} plants not run: {missing[:10]}")
    if extra:
        fail.append(f"plants run that are not in the plan: {extra[:10]}")
    for r in results:
        if r["status"] == "SURVIVED":
            fail.append(f"{r['id']} SURVIVED ({r.get('form')}): {r.get('why', '')}")
        elif r["status"] == "TIMEOUT":
            notrun.append(f"{r['id']} TIMEOUT: a hang is not a kill; raise --timeout or fix the hang")
        elif r["status"] == "FLAKY":
            notrun.append(f"{r['id']} FLAKY: the tests failed without the plant too, so the kill is not counted")
        elif r["status"] != "KILLED":
            notrun.append(f"{r['id']} {r['status']}: {r.get('error', '')}")
        if r.get("restored") is False:
            fail.append(f"{r['id']}: file NOT restored byte-identical")
        if r.get("control") == "RED":
            fail.append(f"{r['id']}: negative control RED twice (tests fail without the plant: not restored or broken)")
        elif r["status"] == "KILLED" and r.get("control") not in ("GREEN", "SKIPPED"):
            notrun.append(f"{r['id']}: no negative control")
    if len(expected_ids) < min_plants:
        notrun.append(f"only {len(expected_ids)} plants, at least {min_plants} needed")
    if not coverage["ok"]:
        notrun.append(f"catalog forms with no plant and no n/a reason: {coverage['missing'] or coverage.get('why')}")
    if fail:
        return "FAIL", fail + notrun
    if notrun:
        return "NOT-RUN", notrun
    return "PASS", []


def git_state(repo: Path, out: Path | None = None) -> dict:
    """head, dirty (uncommitted changes outside the out dir) and whether repo is a git work tree at all."""
    def g(*a: str) -> tuple[int, str]:
        try:
            r = subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)
        except OSError:
            return 1, ""
        return r.returncode, r.stdout.strip()
    rc, top = g("rev-parse", "--show-toplevel")
    if rc != 0:
        return {"head": None, "dirty": False, "git": False}
    _, status = g("status", "--porcelain", "--untracked-files=all", "--", ".")
    root = Path(top).resolve()

    def is_report(line: str) -> bool:
        """An untracked file inside this run's out dir or any earlier prove out dir is not user work."""
        if not line.startswith("??"):
            return False
        p = (root / line[3:].strip('"')).resolve()
        if out is not None and (out == p or out in p.parents):
            return True
        return any((d / OUT_MARKER).is_file() for d in p.parents if root in d.parents)

    lines = [ln for ln in status.splitlines() if ln.strip() and not is_report(ln)]
    return {"head": g("rev-parse", "HEAD")[1] or None, "dirty": bool(lines), "git": True,
            "dirty_files": [ln[3:] for ln in lines[:10]]}


def badge(report: dict) -> str:
    """A static shields.io badge with this run's own numbers; the image URL carries only the text shown."""
    c = report["counts"]
    color = {"PASS": "2ea44f", "FAIL": "d73a49"}.get(report["verdict"], "9a6700")
    msg = f"{c['killed']}/{c['planned']} caught" + ("" if report["verdict"] == "PASS" else f" ({report['verdict']})")
    esc = lambda s: s.replace("-", "--").replace("_", "__").replace(" ", "%20").replace("/", "%2F").replace("(", "%28").replace(")", "%29")  # noqa: E731
    return (f"[![tests proven: {msg}](https://img.shields.io/badge/{esc('tests proven')}-{esc(msg)}-{color})]"
            "(https://github.com/quartercharts-com/prove-your-tests)")


def write_report(out: Path, report: dict) -> None:
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    cov = report["coverage"]
    lines = [f"# Prove your tests: {report['verdict']}", "",
             f"- test command: `{report['test_cmd']}`",
             f"- repo head: {report['git']['head'] or 'not a git repo'}{' (dirty tree)' if report['git']['dirty'] else ''}",
             f"- plants file sha256: {report['plants_sha256'][:12]}, shard {report['shard'] or 'all'}"
             + (f", only {len(report['only'])} named plants" if report.get("only") else ""),
             f"- baseline: {report['baseline']}",
             f"- plants: {report['counts']['planned']} planned, {report['counts']['killed']} killed, "
             f"{report['counts']['survived']} survived, {report['counts']['not_run']} not run",
             f"- catalog ({cov['mode']}): {cov.get('covered', 0)}/{cov.get('total', 0)} forms covered"
             + (f", missing {cov['missing']}" if cov.get("missing") else ""),
             f"- plant authors: {', '.join(report['authors']) or 'unknown'}",
             f"- badge: {report['badge']}" if report.get("badge") else "", ""]
    if report["reasons"]:
        lines += ["## Why not PASS", ""] + [f"- {r}" for r in report["reasons"]] + [""]
    lines += ["## Every plant", "", "| id | form | status | restored | control | seconds | what |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in report["results"]:
        lines.append(f"| {r['id']} | {r.get('form', '')} | {r['status']} | {r.get('restored', '')} | "
                     f"{r.get('control', '')} | {r.get('seconds', '')} | {r.get('why', '').replace('|', '/')[:120]} |")
    (out / "REPORT.md").write_text("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recover", metavar="OUT_DIR")
    ap.add_argument("--repo")
    ap.add_argument("--plants")
    ap.add_argument("--test-cmd")
    ap.add_argument("--out")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--min-plants", type=int, default=25)
    ap.add_argument("--control", choices=["each", "none"], default="each")
    ap.add_argument("--baseline-runs", type=int, default=3,
                    help="run the untouched tests this many times; any red run means flaky tests (NOT-RUN)")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="run on uncommitted changes or a folder that is not a git work tree")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--shard", help="I/N: run every Nth plant starting at I (1-based)")
    args = ap.parse_args(argv)

    if args.recover:
        out = Path(args.recover)
        meta = json.loads((out / "run.json").read_text())
        ok = restore(Path(meta["repo"]), out / "journal.json")
        print("prove: recovered, every file verified" if ok else "prove: RECOVERY INCOMPLETE, check the journal")
        return 0 if ok else 3
    for need in ("repo", "plants", "test_cmd", "out"):
        if not getattr(args, need):
            ap.error(f"--{need.replace('_', '-')} is required (nothing defaults to the current folder)")

    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    journal = out / "journal.json"
    if journal.exists():
        print(f"prove: {journal} exists: a previous run did not finish. Run: prove.py --recover {out}")
        return 3
    if not repo.is_dir():
        print(f"prove: --repo {repo} is not a folder")
        return 2
    if args.baseline_runs < 1:
        ap.error("--baseline-runs must be at least 1")
    state = git_state(repo, out)
    if not args.allow_dirty:
        if not state["git"]:
            print(f"prove: {repo} is not a git work tree, so a crash could not be checked with git status. "
                  "Commit it to git, or pass --allow-dirty.")
            return 2
        if state["dirty"]:
            print(f"prove: {repo} has uncommitted changes {state['dirty_files']}. Commit or stash them first "
                  "(a plant must never mix with your own edits), or pass --allow-dirty.")
            return 2
    out.mkdir(parents=True, exist_ok=True)
    (out / OUT_MARKER).write_text("prove-your-tests report folder\n")
    (out / "run.json").write_text(json.dumps({"repo": str(repo)}))

    doc, bad = plants_schema.load(args.plants)
    bad = bad or plants_schema.problems(doc)
    if bad:  # a bad or partial plants file, from any model, never runs and never crashes
        for b in bad[:30]:
            print(f"prove: plants file: {b}")
        print("prove: NOT-RUN, the plants file is not usable")
        return 2
    plants = doc["plants"]
    digest = plants_digest(plants)
    if doc.get("plants_sha256") and doc["plants_sha256"] != digest:
        print("prove: plants_sha256 does not match the plants (file edited after it was sealed)")
        return 2
    ids = [p["id"] for p in plants]
    if len(ids) != len(set(ids)):
        print("prove: duplicate plant ids")
        return 2
    selected = plants
    if args.only:
        selected = [p for p in plants if p["id"] in set(args.only)]
    if args.shard:
        i, n = (int(x) for x in args.shard.split("/"))
        selected = selected[i - 1::n]
    expected = [p["id"] for p in selected]
    coverage = coverage_report(doc, plants)

    # Ctrl-C, kill, a closed terminal (HUP) and QUIT all restore before exiting; only SIGKILL cannot
    # be caught, and the journal plus --recover covers that.
    caught = [s for s in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT") if hasattr(signal, s)]
    old_handlers = {s: signal.signal(getattr(signal, s), _raise_interrupt) for s in caught}
    results: list[dict] = []
    restore_failed = False
    baseline, base_tail = "NOT-RUN", ""
    try:
        for n in range(args.baseline_runs):
            outcome, _, base_s, base_tail = run_tests(args.test_cmd, repo, args.timeout)
            print(f"prove: baseline run {n + 1}/{args.baseline_runs} {outcome} in {base_s:.1f}s")
            if outcome != "PASSED":
                baseline = outcome if n == 0 else f"FLAKY (run {n + 1} of {args.baseline_runs} was {outcome})"
                break
            baseline = "PASSED"
        if baseline == "PASSED":
            for p in selected:
                r = {"id": p["id"], "form": p.get("form"), "why": p.get("why", ""), "author": p.get("author")}
                problem = check_plant(p, repo)
                if problem:
                    r.update(status="STALE", error=problem)
                    results.append(r)
                    continue
                try:
                    apply_plant(p, repo, journal)
                    outcome, rc, secs, tail = run_tests(args.test_cmd, repo, args.timeout)
                except OSError as exc:  # a write failed (read-only file, disk full): nothing was tested
                    outcome, secs, tail = "NOT-APPLIED", 0.0, ""
                    r["error"] = f"could not apply the plant: {exc}"
                finally:
                    r["restored"] = restore(repo, journal)
                    restore_failed |= not r["restored"]
                r["seconds"] = round(secs, 2)
                r["status"] = {"PASSED": "SURVIVED", "FAILED": "KILLED", "TIMEOUT": "TIMEOUT",
                               "NOT-APPLIED": "NOT-APPLIED"}[outcome]
                if outcome == "PASSED":
                    r["test_output_tail"] = tail
                if r["status"] == "KILLED":
                    if args.control == "each" and r["restored"]:
                        c, _, _, ctail = run_tests(args.test_cmd, repo, args.timeout)
                        if c != "PASSED":  # once more: a flaky suite is not a kill, a broken tree is a FAIL
                            r["control_output_tail"] = ctail  # the first red run is the evidence; keep it
                            c2, _, _, ctail = run_tests(args.test_cmd, repo, args.timeout)
                            r["control_rerun_tail"] = ctail
                            if c2 == "PASSED":
                                r["status"], c = "FLAKY", "PASSED"
                        r["control"] = "GREEN" if c == "PASSED" else "RED"
                    elif args.control == "none":
                        r["control"] = "SKIPPED"
                results.append(r)
                print(f"prove: {r['id']} {r['status']} control={r.get('control', '-')} ({r['seconds']}s)")
                if restore_failed:
                    break
    except Interrupted as exc:
        restore_failed |= not restore(repo, journal)
        print(f"prove: interrupted ({exc}); files {'restored' if not restore_failed else 'NOT restored'}")
    except BaseException:
        # any other crash: put the files back first, then let the error show
        if not restore(repo, journal):
            print(f"prove: CRASHED and files NOT restored. Run: prove.py --recover {out}", file=sys.stderr)
        raise
    finally:
        for s, h in old_handlers.items():
            signal.signal(getattr(signal, s), h)

    if args.control == "none":
        # a run without the control can still find SURVIVED plants, but it can never PASS
        coverage = {**coverage, "ok": False, "why": "--control none: no negative control, cannot PASS"}
    min_plants = args.min_plants if not (args.only or args.shard) else 0
    v, reasons = verdict(baseline, results, expected, min_plants, coverage)
    report = {"verdict": v, "reasons": reasons, "test_cmd": args.test_cmd, "git": git_state(repo, out),
              "plants_file": str(args.plants), "plants_sha256": digest, "shard": args.shard,
              "only": args.only, "baseline": baseline, "baseline_tail": base_tail if baseline != "PASSED" else "",
              "coverage": coverage, "authors": sorted({str(p.get("author")) for p in selected}),
              "counts": {"planned": len(expected),
                         "killed": sum(r["status"] == "KILLED" and r.get("control") in ("GREEN", "SKIPPED")
                                       for r in results),
                         "survived": sum(r["status"] == "SURVIVED" for r in results),
                         "not_run": len(expected) - sum(r["status"] in ("KILLED", "SURVIVED") for r in results)},
              "results": results}
    report["badge"] = badge(report)
    write_report(out, report)
    c = report["counts"]
    print(f"prove: badge for your README (a static image, nothing is sent anywhere): {report['badge']}")
    print(f"prove: {v}: {c['killed']}/{c['planned']} killed, {c['survived']} survived, {c['not_run']} not run; "
          f"catalog {coverage.get('covered', 0)}/{coverage.get('total', 0)} -> {out / 'REPORT.md'}")
    if restore_failed:
        return 3
    return {"PASS": 0, "FAIL": 1}.get(v, 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
