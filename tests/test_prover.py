"""Self-test: the prover keeps its promises, or this test goes red.

1. PASS only when the baseline was green, every planned plant ran and was KILLED, every touched file came
   back byte-identical, created files and folders are gone, and the control run after restore was green.
2. Anything not run (stale or ambiguous plant, interrupted run, missing shard, too few plants, a catalog
   form with no plant and no reason, a red or timed-out baseline) is NOT-RUN, never PASS.
3. A SURVIVED plant, a failed restore, a red control, a duplicate or extra plant id, or shards that ran a
   different plants file or head is FAIL.
4. A crash leaves a journal; --recover restores; a new run refuses while a journal exists.
   Exit codes: 0 PASS, 1 FAIL, 2 NOT-RUN or bad input, 3 restore failed.

Every case runs in its own temporary folder, never in this repo.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skill" / "prove-your-tests" / "scripts"
PY = sys.executable
CALC = "def is_adult(age):\n    return age >= 18\n\n\ndef label(age):\n    return 'adult' if is_adult(age) else 'minor'\n"
STRONG = ("import unittest\nimport calc\n\n\nclass T(unittest.TestCase):\n"
          "    def test_line(self):\n        self.assertTrue(calc.is_adult(18))\n        self.assertFalse(calc.is_adult(17))\n"
          "    def test_label(self):\n        self.assertEqual(calc.label(40), 'adult')\n        self.assertEqual(calc.label(3), 'minor')\n")
WEAK = ("import unittest\nimport calc\n\n\nclass T(unittest.TestCase):\n"
        "    def test_one(self):\n        self.assertTrue(calc.is_adult(30))\n")
TEST_CMD = f"{PY} -m unittest -q test_calc"
ALL_M = [f"M{i}" for i in range(1, 10)]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def edit(old: str, new: str, file: str = "calc.py", **extra) -> dict:
    return {"file": file, "old": old, "new": new, **extra}


def plant(pid: str, *edits: dict, form: str = "M1") -> dict:
    return {"id": pid, "form": form, "author": "self-test", "why": pid, "edits": list(edits)}


KILL_A = edit("age >= 18", "age > 18")
KILL_B = edit("age >= 18", "age >= 17", )
KILL_C = edit("'adult' if", "'minor' if")
SURVIVES_WEAK = edit("age >= 18", "age > 18")


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pyt-selftest-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "calc.py").write_text(CALC)
        (self.repo / "test_calc.py").write_text(STRONG)
        self.orig = sha(self.repo / "calc.py")
        self.n = 0
        self.git("init", "-q")
        self.commit()

    def git(self, *a):
        return subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=selftest", *a],
                              cwd=self.repo, capture_output=True, text=True)

    def commit(self):
        """The prover refuses uncommitted work, so each case commits its own setup first."""
        self.git("add", "-A")
        if self.git("status", "--porcelain").stdout.strip():
            self.git("commit", "-qm", "case setup")

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp):
            for name in dirs + files:
                try:
                    os.chmod(Path(root) / name, stat.S_IRWXU)
                except OSError:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plants_file(self, plants, mode="behavior", coverage=None, seal=False, name=None):
        planted = {p["form"] for p in plants}
        if coverage is None:
            coverage = [{"form": f, "na": "not in this tiny file"} for f in ALL_M if f not in planted]
        doc = {"version": 1, "plants": plants, "coverage": coverage}
        if mode is not None:
            doc["mode"] = mode
        if seal:
            doc["plants_sha256"] = hashlib.sha256(json.dumps(plants, sort_keys=True).encode()).hexdigest()
        self.n += 1
        path = self.tmp / (name or f"plants{self.n}.json")
        path.write_text(json.dumps(doc))
        return path

    def prove(self, plants_path, *extra, cmd=TEST_CMD, out=None, timeout=20, commit=True, runs=None):
        """runs: --baseline-runs, for commands that count their own calls (default: the prover's 3)."""
        if commit:
            self.commit()
        out = out or self.tmp / f"out{self.n}-{len(list(self.tmp.glob('out*')))}"
        args = [PY, str(SCRIPTS / "prove.py"), "--repo", str(self.repo), "--plants", str(plants_path),
                "--test-cmd", cmd, "--out", str(out), "--timeout", str(timeout), *extra]
        if runs is not None:
            args += ["--baseline-runs", str(runs)]
        # like CI: bytecode writing on, whatever the developer's shell says
        env = {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}
        r = subprocess.run(args, capture_output=True, text=True, timeout=300, env=env)
        rep = json.loads((out / "report.json").read_text()) if (out / "report.json").exists() else None
        return r.returncode, rep, out, r.stdout + r.stderr

    def assert_clean(self):
        self.assertEqual(sha(self.repo / "calc.py"), self.orig, "calc.py not restored byte-identical")


class Verdicts(Case):
    def test_pass_when_everything_is_killed_restored_and_green_again(self):
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B), plant("P3", KILL_C, form="M4")])
        rc, rep, _, log = self.prove(p, "--min-plants", "3")
        self.assertEqual(rc, 0, log)
        self.assertEqual(rep["verdict"], "PASS")
        self.assertEqual([r["status"] for r in rep["results"]], ["KILLED"] * 3)
        self.assertTrue(all(r["restored"] is True and r["control"] == "GREEN" for r in rep["results"]))
        self.assertEqual(rep["counts"], {"planned": 3, "killed": 3, "survived": 0, "not_run": 0})
        self.assertEqual(rep["reasons"], [])
        self.assert_clean()

    def test_survivor_is_fail_with_exit_1(self):
        (self.repo / "test_calc.py").write_text(WEAK)
        p = self.plants_file([plant("P1", SURVIVES_WEAK), plant("P2", edit("return age >= 18", "return False"), form="M6")])
        rc, rep, _, log = self.prove(p, "--min-plants", "2")
        self.assertEqual(rc, 1, log)
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertEqual([r["status"] for r in rep["results"]], ["SURVIVED", "KILLED"])
        self.assertEqual(rep["counts"], {"planned": 2, "killed": 1, "survived": 1, "not_run": 0})
        self.assert_clean()

    def test_fail_beats_not_run(self):
        (self.repo / "test_calc.py").write_text(WEAK)
        p = self.plants_file([plant("P1", SURVIVES_WEAK)])
        rc, rep, _, log = self.prove(p)  # survivor AND too few plants
        self.assertEqual((rc, rep["verdict"]), (1, "FAIL"), log)

    def test_red_baseline_runs_no_plant(self):
        (self.repo / "test_calc.py").write_text(STRONG.replace("calc.label(3), 'minor'", "calc.label(3), 'adult'"))
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["results"], [])
        self.assert_clean()

    def test_timed_out_baseline_is_not_green(self):
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", cmd=f"{PY} -c 'import time; time.sleep(30)'", timeout=1)
        self.assertEqual((rc, rep["verdict"], rep["baseline"]), (2, "NOT-RUN", "TIMEOUT"), log)

    def test_default_minimum_is_25(self):
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B)])
        rc, rep, _, log = self.prove(p)
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertTrue(any("at least 25" in x for x in rep["reasons"]), rep["reasons"])

    def test_minimum_is_exact(self):
        plants = [plant(f"P{i:02d}", KILL_A) for i in range(1, 26)]
        rc, rep, _, log = self.prove(self.plants_file(plants[:24]))
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        rc, rep, _, log = self.prove(self.plants_file(plants))
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)
        self.assert_clean()

    def test_timeout_under_a_plant_is_not_run_not_a_kill(self):
        loop = edit("return age >= 18", "while True:\n        pass")
        p = self.plants_file([plant("P1", loop, form="M6"), plant("P2", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "2", timeout=10)
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["results"][0]["status"], "TIMEOUT")
        self.assertEqual(rep["counts"]["killed"], 1, "a hang must never count as a kill")
        self.assertTrue(any("TIMEOUT" in x for x in rep["reasons"]), rep["reasons"])
        self.assert_clean()

    def test_edits_on_one_file_apply_in_order(self):
        first = edit("age >= 18", "age >= LIMIT")
        second = edit("def is_adult(age):", "LIMIT = 21\n\n\ndef is_adult(age):")
        third = edit("LIMIT = 21", "LIMIT = 19")  # exists only after the second edit
        p = self.plants_file([plant("P1", first, second, third)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)
        self.assert_clean()

    def test_control_none_never_passes(self):
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", "--control", "none")
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["results"][0]["control"], "SKIPPED")


class Controls(Case):
    COUNTER = ("n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               "if [ $n -eq 0 ]; then {t}; elif [ $n -eq 1 ]; then exit 1; else {after}; fi")

    def cmd(self, after):
        return self.COUNTER.format(c=self.tmp / "count", t=TEST_CMD, after=after)

    def test_red_control_is_fail(self):
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", cmd=self.cmd("exit 1"), runs=1)
        self.assertEqual((rc, rep["verdict"]), (1, "FAIL"), log)
        self.assertEqual(rep["results"][0]["control"], "RED")
        self.assertEqual(rep["counts"]["killed"], 0, "a kill whose control stayed red is not a kill")

    def test_timed_out_control_is_red(self):
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", cmd=self.cmd("sleep 60"), timeout=10, runs=1)
        self.assertEqual((rc, rep["verdict"]), (1, "FAIL"), log)
        self.assertEqual(rep["results"][0]["control"], "RED")
        self.assertEqual(rep["counts"]["killed"], 0, "a kill whose control stayed red is not a kill")

    def test_control_red_once_then_green_is_flaky_not_a_kill(self):
        # baseline green, plant run red, control red, control again green: the suite is flaky
        c = self.tmp / "count"
        cmd = (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               f"if [ $n -eq 0 ] || [ $n -ge 3 ]; then {TEST_CMD}; else exit 1; fi")
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", cmd=cmd, runs=1)
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["results"][0]["status"], "FLAKY")
        self.assertEqual(rep["counts"]["killed"], 0)
        self.assertIn("control_output_tail", rep["results"][0], "the first red control is the evidence of the flake")
        self.assertIn("control_rerun_tail", rep["results"][0])
        self.assert_clean()

    def test_flaky_baseline_runs_no_plant(self):
        c = self.tmp / "count"
        cmd = f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; if [ $n -eq 1 ]; then exit 1; fi; {TEST_CMD}"
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", cmd=cmd)
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertTrue(rep["baseline"].startswith("FLAKY"), rep["baseline"])
        self.assertEqual(rep["results"], [])


class BadPlants(Case):
    def test_stale_plant_is_not_run(self):
        stale = dict(KILL_A, file_sha256="0" * 64)
        p = self.plants_file([plant("P1", stale), plant("P2", KILL_B)])
        rc, rep, _, log = self.prove(p, "--min-plants", "2")
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["results"][0]["status"], "STALE")
        self.assert_clean()

    def test_right_sha_is_accepted(self):
        good = dict(KILL_A, file_sha256=self.orig)
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", good)]), "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)

    def test_ambiguous_old_is_not_run(self):
        (self.repo / "calc.py").write_text(CALC + "\n\ndef again(age):\n    return age >= 18\n")
        self.orig = sha(self.repo / "calc.py")
        p = self.plants_file([plant("P1", edit("return age >= 18", "return age > 18"))])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"], rep["results"][0]["status"]), (2, "NOT-RUN", "STALE"), log)
        self.assert_clean()

    def test_offsets_must_match(self):
        bad = {"file": "calc.py", "start": 0, "end": 3, "old": "xyz", "new": "abc"}
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", bad)]), "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "STALE"), log)
        start = CALC.index("age >= 18")
        good = {"file": "calc.py", "start": start, "end": start + 9, "old": "age >= 18", "new": "age > 18"}
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", good)]), "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)
        self.assert_clean()

    def test_edited_sealed_file_is_refused(self):
        p = self.plants_file([plant("P1", KILL_A)], seal=True)
        doc = json.loads(p.read_text())
        doc["plants"][0]["edits"][0]["new"] = "age >= 18"  # softened after sealing
        p.write_text(json.dumps(doc))
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual(rc, 2, log)
        self.assertIsNone(rep)
        sealed = self.plants_file([plant("P1", KILL_A)], seal=True)
        rc, rep, _, log = self.prove(sealed, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)

    def test_duplicate_ids_are_refused(self):
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A), plant("P1", KILL_B)]), "--min-plants", "1")
        self.assertEqual((rc, rep), (2, None), log)

    def test_outside_repo_is_refused(self):
        outside = self.tmp / "outside.py"
        outside.write_text("X = 1\n")
        p = self.plants_file([plant("P1", edit("X = 1", "X = 2", file="../outside.py"))])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "STALE"), log)
        self.assertEqual(outside.read_text(), "X = 1\n")

    def test_create_over_existing_file_is_refused(self):
        (self.repo / "keep.py").write_text("KEEP = True\n")
        p = self.plants_file([plant("P1", {"file": "keep.py", "create": "KEEP = False\n"}, KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "STALE"), log)
        self.assertEqual((self.repo / "keep.py").read_text(), "KEEP = True\n")
        self.assert_clean()


class CreatedFiles(Case):
    def test_created_file_and_new_folders_are_removed(self):
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "__init__.py").write_text("")
        mk = {"file": "pkg/deep/er/evil.py", "create": "OVERRIDE = True\n"}
        mk2 = {"file": "newtop/x.py", "create": "Y = 1\n"}
        use = edit("    return age >= 18", "    import importlib\n    importlib.import_module('newtop.x')\n    return age > 18")
        p = self.plants_file([plant("P1", mk, mk2, use, form="M2")])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)
        self.assertFalse((self.repo / "pkg" / "deep").exists())
        self.assertFalse((self.repo / "newtop").exists())
        self.assertTrue((self.repo / "pkg" / "__init__.py").exists(), "a folder that already existed was removed")
        self.assert_clean()

    def test_empty_folder_that_existed_is_kept(self):
        (self.repo / "empty").mkdir()
        p = self.plants_file([plant("P1", {"file": "empty/new.py", "create": "Z = 1\n"}, KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual(rc, 0, log)
        self.assertTrue((self.repo / "empty").is_dir())
        self.assertFalse((self.repo / "empty" / "new.py").exists())


class Coverage(Case):
    def test_missing_form_is_not_run(self):
        p = self.plants_file([plant("P1", KILL_A)], coverage=[{"form": f, "na": "x"} for f in ALL_M[1:8]])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["coverage"]["missing"], ["M9"])

    def test_blank_reason_is_not_a_reason(self):
        cov = [{"form": f, "na": "x"} for f in ALL_M[1:8]] + [{"form": "M9", "na": "   "}]
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)], coverage=cov), "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)

    def test_no_mode_is_not_run(self):
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)], mode=None), "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertFalse(rep["coverage"]["ok"])

    def test_guard_mode_needs_all_15_forms(self):
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A, form="E1")], mode="guard", coverage=[]),
                                     "--min-plants", "1")
        self.assertEqual((rc, rep["coverage"]["covered"], rep["coverage"]["total"]), (2, 1, 15), log)


class CrashAndRecover(Case):
    def crash_cmd(self, extra=""):
        c = self.tmp / "count"
        return (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
                f"if [ $n -eq 0 ]; then {TEST_CMD}; else {extra} kill -9 $PPID; sleep 5; fi")

    def test_kill_leaves_a_journal_recover_restores(self):
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B)])
        out = self.tmp / "crash-out"
        rc, rep, _, log = self.prove(p, "--min-plants", "2", cmd=self.crash_cmd(), out=out, runs=1)
        self.assertNotEqual(rc, 0, log)
        self.assertTrue((out / "journal.json").exists(), "no journal after a crash")
        self.assertNotEqual(sha(self.repo / "calc.py"), self.orig, "the plant should still be in place")
        rc2, _, _, log2 = self.prove(p, "--min-plants", "2", out=out, commit=False)
        self.assertEqual(rc2, 3, "a new run must refuse while a journal exists: " + log2)
        self.assertNotEqual(sha(self.repo / "calc.py"), self.orig)
        r = subprocess.run([PY, str(SCRIPTS / "prove.py"), "--recover", str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((out / "journal.json").exists())
        self.assert_clean()

    def test_incomplete_recovery_is_exit_3(self):
        p = self.plants_file([plant("P1", KILL_A)])
        out = self.tmp / "crash-out"
        self.prove(p, "--min-plants", "1", cmd=self.crash_cmd(), out=out, runs=1)
        os.chmod(self.repo / "calc.py", stat.S_IRUSR)
        r = subprocess.run([PY, str(SCRIPTS / "prove.py"), "--recover", str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertTrue((out / "journal.json").exists(), "the journal must stay until the restore is verified")

    def test_restore_failure_during_a_run_is_exit_3(self):
        c = self.tmp / "count"
        cmd = (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               f"if [ $n -eq 0 ]; then {TEST_CMD}; else chmod 400 {self.repo / 'calc.py'}; exit 1; fi")
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B)])
        rc, rep, out, log = self.prove(p, "--min-plants", "2", cmd=cmd, runs=1)
        self.assertEqual(rc, 3, log)
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertIs(rep["results"][0]["restored"], False)
        self.assertEqual(len(rep["results"]), 1, "the run must stop after a failed restore")
        self.assertTrue((out / "journal.json").exists())

    def test_sigterm_restores_and_is_not_run(self):
        c = self.tmp / "count"
        cmd = (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               f"if [ $n -eq 0 ]; then {TEST_CMD}; else kill -TERM $PPID; sleep 5; exit 1; fi")
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B)])
        rc, rep, out, log = self.prove(p, "--min-plants", "2", cmd=cmd, runs=1)
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertEqual(rep["results"], [])
        self.assertFalse((out / "journal.json").exists())
        self.assert_clean()


class Safety(Case):
    """A plant must never be left in a user's repo, whatever goes wrong."""

    def test_dirty_tree_is_refused_and_untouched(self):
        (self.repo / "calc.py").write_text(CALC + "# my unsaved work\n")
        before = sha(self.repo / "calc.py")
        rc, rep, out, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1", commit=False)
        self.assertEqual(rc, 2, log)
        self.assertIsNone(rep, "nothing may run on a dirty tree")
        self.assertIn("uncommitted", log)
        self.assertEqual(sha(self.repo / "calc.py"), before)

    def test_untracked_file_counts_as_dirty(self):
        (self.repo / "notes.txt").write_text("mine\n")
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1", commit=False)
        self.assertEqual((rc, rep), (2, None), log)

    def test_allow_dirty_runs_and_keeps_the_user_edit(self):
        (self.repo / "calc.py").write_text(CALC + "# my unsaved work\n")
        before = sha(self.repo / "calc.py")
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1",
                                     "--allow-dirty", commit=False)
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)
        self.assertTrue(rep["git"]["dirty"])
        self.assertEqual(sha(self.repo / "calc.py"), before)

    def test_not_a_git_repo_is_refused_without_allow_dirty(self):
        shutil.rmtree(self.repo / ".git")
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", commit=False)
        self.assertEqual((rc, rep), (2, None), log)
        rc, rep, _, log = self.prove(p, "--min-plants", "1", "--allow-dirty", commit=False)
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)

    def test_out_dir_inside_the_repo_is_not_user_work(self):
        out = self.repo / ".prove-out" / "run"
        p = self.plants_file([plant("P1", KILL_A)])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", out=out)
        self.assertEqual(rc, 0, log)
        rc, rep, _, log = self.prove(p, "--min-plants", "1", out=self.repo / ".prove-out" / "run2", commit=False)
        self.assertEqual((rc, rep["verdict"], rep["git"]["dirty"]), (0, "PASS", False), log)

    def test_non_utf8_file_is_stale_not_a_crash(self):
        # Python 3.14 refuses non-UTF-8 source without a coding line, so declare latin-1: the file runs under the
        # tests, and the prover (UTF-8 only) must still call it STALE and leave it untouched.
        (self.repo / "calc.py").write_bytes(b"# -*- coding: latin-1 -*-\n# caf\xe9\n" + CALC.encode())
        before = sha(self.repo / "calc.py")
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"], rep["results"][0]["status"]), (2, "NOT-RUN", "STALE"), log)
        self.assertIn("UTF-8", rep["results"][0]["error"])
        self.assertEqual(sha(self.repo / "calc.py"), before)

    def test_crlf_file_comes_back_byte_identical(self):
        (self.repo / "calc.py").write_bytes(CALC.replace("\n", "\r\n").encode())
        before = sha(self.repo / "calc.py")
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1")
        self.assertEqual(rc, 0, log)
        self.assertEqual(sha(self.repo / "calc.py"), before)

    def test_no_op_plant_is_stale(self):
        p = self.plants_file([plant("P1", edit("age >= 18", "age >= 18"))])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "STALE"), log)
        self.assertIn("changes nothing", rep["results"][0]["error"])

    def test_read_only_file_is_not_applied_and_leaves_no_journal(self):
        os.chmod(self.repo / "calc.py", stat.S_IRUSR)
        rc, rep, out, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "NOT-APPLIED"), log)
        self.assertFalse((out / "journal.json").exists(), "an unchanged read-only file must count as restored")
        self.assert_clean()

    def test_second_file_write_fails_first_file_is_put_back(self):
        (self.repo / "b.py").write_text("X = 1\n")
        self.commit()
        os.chmod(self.repo / "b.py", stat.S_IRUSR)
        p = self.plants_file([plant("P1", KILL_A, edit("X = 1", "X = 2", file="b.py"))])
        rc, rep, out, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "NOT-APPLIED"), log)
        self.assertIs(rep["results"][0]["restored"], True)
        self.assertFalse((out / "journal.json").exists())
        self.assert_clean()

    def test_symlink_to_a_file_outside_the_repo_is_refused(self):
        outside = self.tmp / "outside.py"
        outside.write_text(CALC)
        (self.repo / "link.py").symlink_to(outside)
        before = sha(outside)
        p = self.plants_file([plant("P1", edit("age >= 18", "age > 18", file="link.py"))])
        rc, rep, _, log = self.prove(p, "--min-plants", "1")
        self.assertEqual((rc, rep["results"][0]["status"]), (2, "STALE"), log)
        self.assertEqual(sha(outside), before)

    def test_planted_bytes_are_exact_utf8_with_no_newline_translation(self):
        # the test command snapshots calc.py while the plant is in place
        c, snap = self.tmp / "count", self.tmp / "snapshot.py"
        cmd = (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               f"if [ $n -eq 1 ]; then cp calc.py {snap}; exit 1; fi; {TEST_CMD}")
        new = "'adulté é€' if"
        p = self.plants_file([plant("P1", edit("'adult' if", new))])
        rc, rep, _, log = self.prove(p, "--min-plants", "1", cmd=cmd, runs=1)
        self.assertEqual(rc, 0, log)
        self.assertEqual(snap.read_bytes(), CALC.replace("'adult' if", new).encode("utf-8"),
                         "the planted file must be exactly the planted text as UTF-8, LF kept")
        self.assert_clean()

    def test_planted_file_deleted_during_the_run_is_put_back(self):
        c = self.tmp / "count"
        cmd = (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               f"if [ $n -eq 1 ]; then rm calc.py; exit 1; fi; {TEST_CMD}")
        rc, rep, out, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1", cmd=cmd, runs=1)
        self.assertEqual((rc, rep["results"][0]["restored"]), (0, True), log)
        self.assertFalse((out / "journal.json").exists())
        self.assert_clean()

    def test_journal_is_fsynced_before_any_file_changes(self):
        sys.path.insert(0, str(SCRIPTS))
        import prove as runner
        journal = self.tmp / "journal.json"
        calls = []
        real = runner.os.fsync

        def watch(fd):
            calls.append((journal.with_suffix(".tmp").exists(), sha(self.repo / "calc.py") == self.orig))
            return real(fd)

        runner.os.fsync = watch
        try:
            runner.apply_plant(plant("P1", KILL_A), self.repo.resolve(), journal)
        finally:
            runner.os.fsync = real
        self.assertTrue(calls, "the journal was never fsynced")
        self.assertEqual(calls[0], (True, True), "fsync must happen on the journal before the file changes")
        self.assertNotEqual(sha(self.repo / "calc.py"), self.orig)
        self.assertTrue(runner.restore(self.repo.resolve(), journal))
        self.assert_clean()

    def test_hangup_restores_like_sigterm(self):
        c = self.tmp / "count"
        cmd = (f"n=$(cat {c} 2>/dev/null || echo 0); echo $((n+1)) > {c}; "
               f"if [ $n -eq 0 ]; then {TEST_CMD}; else kill -HUP $PPID; sleep 5; exit 1; fi")
        rc, rep, out, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1", cmd=cmd, runs=1)
        self.assertEqual((rc, rep["verdict"]), (2, "NOT-RUN"), log)
        self.assertFalse((out / "journal.json").exists())
        self.assert_clean()

    def test_real_kill_9_from_outside_then_recover(self):
        p = self.plants_file([plant("P1", KILL_A)])
        self.commit()
        out = self.tmp / "kill-out"
        log = self.tmp / "kill-run.log"
        with open(log, "w") as fh:
            proc = subprocess.Popen([PY, str(SCRIPTS / "prove.py"), "--repo", str(self.repo), "--plants", str(p),
                                     "--test-cmd", f"{TEST_CMD} && sleep 5", "--out", str(out), "--min-plants", "1",
                                     "--baseline-runs", "1"], stdout=fh, stderr=subprocess.STDOUT)
            # kill only after two positive signs that the plant is in: the journal exists and the file changed
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and proc.poll() is None and not (
                    (out / "journal.json").exists() and sha(self.repo / "calc.py") != self.orig):
                time.sleep(0.02)
            planted = (out / "journal.json").exists() and sha(self.repo / "calc.py") != self.orig
            exited = proc.poll()
            os.kill(proc.pid, signal.SIGKILL) if exited is None else None
            proc.wait()
        self.assertTrue(planted, f"the plant never went in (runner exit {exited}); runner output:\n{log.read_text()}")
        r = subprocess.run([PY, str(SCRIPTS / "prove.py"), "--recover", str(out)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_clean()
        self.assertEqual(self.git("status", "--porcelain").stdout.strip(), "")

    def test_restore_reads_the_bytes_back_after_writing(self):
        sys.path.insert(0, str(SCRIPTS))
        import prove as runner
        journal = self.tmp / "journal.json"
        runner.apply_plant(plant("P1", KILL_A), self.repo.resolve(), journal)
        real = Path.write_bytes
        Path.write_bytes = lambda p, data: real(p, data[:-1])  # a write that reports success but lands short
        try:
            self.assertFalse(runner.restore(self.repo.resolve(), journal), "a short write must not count as restored")
        finally:
            Path.write_bytes = real
        self.assertTrue(journal.exists(), "the journal must stay until the restore is verified")
        self.assertTrue(runner.restore(self.repo.resolve(), journal))
        self.assert_clean()

    def test_a_crash_inside_the_loop_restores_and_still_raises(self):
        sys.path.insert(0, str(SCRIPTS))
        import prove as runner
        self.commit()
        p = self.plants_file([plant("P1", KILL_A)])
        out = self.tmp / "crash-loop-out"
        real, calls = runner.run_tests, []

        def boom(*a, **k):
            calls.append(sha(self.repo / "calc.py") != self.orig)
            if len(calls) > 1:
                raise RuntimeError("boom inside the loop")
            return real(*a, **k)

        runner.run_tests = boom
        try:
            with self.assertRaises(RuntimeError, msg="a crash must not be swallowed into a report"):
                runner.main(["--repo", str(self.repo), "--plants", str(p), "--test-cmd", TEST_CMD,
                             "--out", str(out), "--min-plants", "1", "--baseline-runs", "1"])
        finally:
            runner.run_tests = real
        self.assertEqual(calls, [False, True], "the crash must come while the plant is in")
        self.assert_clean()
        self.assertFalse((out / "journal.json").exists())
        self.assertFalse((out / "report.json").exists(), "no report may be written from a crashed run")


class Bytecode(Case):
    """Python bytecode caches must never block a run or stand in for a planted or restored file."""

    def test_untracked_bytecode_cache_is_not_user_work(self):
        (self.repo / "__pycache__").mkdir()
        (self.repo / "__pycache__" / "calc.cpython-312.pyc").write_bytes(b"cache")
        (self.repo / ".pytest_cache").mkdir()
        (self.repo / ".pytest_cache" / "v").write_text("x")
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", KILL_A)]), "--min-plants", "1", commit=False)
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)

    def test_runs_write_no_bytecode_into_the_repo(self):
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B)])
        rc, rep, _, log = self.prove(p, "--min-plants", "2")
        self.assertEqual(rc, 0, log)
        self.assertEqual(list(self.repo.rglob("*.pyc")), [], "the runner must not leave bytecode behind")
        rc, rep, _, log = self.prove(p, "--min-plants", "2", commit=False)
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), "a second run in the same repo must not be refused: " + log)

    def test_mtime_moves_at_least_one_second_on_plant_and_restore(self):
        sys.path.insert(0, str(SCRIPTS))
        import prove as runner
        f = self.repo / "calc.py"
        now = time.time_ns()
        os.utime(f, ns=(now, now))
        journal = self.tmp / "journal.json"
        runner.apply_plant(plant("P1", KILL_B), self.repo.resolve(), journal)
        planted = f.stat().st_mtime_ns
        self.assertGreaterEqual(planted, now + 1_000_000_000)
        self.assertTrue(runner.restore(self.repo.resolve(), journal))
        self.assertGreaterEqual(f.stat().st_mtime_ns, planted + 1_000_000_000)
        self.assert_clean()


class Badge(Case):
    def test_badge_shows_this_runs_numbers_and_nothing_else(self):
        p = self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B)])
        rc, rep, out, log = self.prove(p, "--min-plants", "2")
        self.assertEqual(rc, 0, log)
        self.assertEqual(rep["badge"], "[![tests proven: 2/2 caught](https://img.shields.io/badge/tests%20proven-2%2F2%20caught-2ea44f)]"
                                       "(https://github.com/quartercharts-com/prove-your-tests)")
        self.assertIn(rep["badge"], (out / "REPORT.md").read_text())
        self.assertIn(rep["badge"], log)
        (self.repo / "test_calc.py").write_text(WEAK)
        rc, rep, _, log = self.prove(self.plants_file([plant("P1", SURVIVES_WEAK)]), "--min-plants", "1")
        self.assertEqual(rc, 1, log)
        self.assertIn("0%2F1%20caught%20%28FAIL%29-d73a49", rep["badge"])
        self.assertNotIn(str(self.tmp), rep["badge"], "the badge must carry no path or name from the run")


class Shards(Case):
    def four(self):
        return self.plants_file([plant("P1", KILL_A), plant("P2", KILL_B), plant("P3", KILL_C, form="M4"),
                                 plant("P4", edit("'minor'", "'adult'"), form="M4")], name="four.json")

    def union(self, plants, *dirs, extra=()):
        r = subprocess.run([PY, str(SCRIPTS / "union.py"), "--plants", str(plants), *extra, *map(str, dirs)],
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def shard(self, p, spec):
        out = self.tmp / f"shard{spec.replace('/', 'of')}"
        rc, rep, out, log = self.prove(p, "--shard", spec, out=out)
        self.assertEqual(rc, 0, log)
        return out, rep

    def test_shards_split_exactly_and_join(self):
        p = self.four()
        a, ra = self.shard(p, "1/2")
        b, rb = self.shard(p, "2/2")
        self.assertEqual([r["id"] for r in ra["results"]], ["P1", "P3"])
        self.assertEqual([r["id"] for r in rb["results"]], ["P2", "P4"])
        self.assertEqual(self.union(p, a, b, extra=("--min-plants", "4"))[0], 0)
        self.assertEqual(self.union(p, a, extra=("--min-plants", "4"))[0], 2, "a missing shard is NOT-RUN")
        rc, log = self.union(p, a, b)
        self.assertEqual(rc, 2, "union default minimum must be 25")
        self.assertIn("at least 25 needed", log)
        self.assertEqual(self.union(p, a, a, b, extra=("--min-plants", "4"))[0], 1, "a shard counted twice is FAIL")
        doc = json.loads((b / "report.json").read_text())
        del doc["results"][0]["control"]
        (b / "report.json").write_text(json.dumps(doc))
        rc, log = self.union(p, a, b, extra=("--min-plants", "4"))
        self.assertEqual(rc, 2, "a kill with no control recorded is NOT-RUN: " + log)
        self.assertIn("no negative control", log)
        self.assert_clean()

    def test_union_rejects_other_files_heads_and_extra_ids(self):
        p = self.four()
        a, _ = self.shard(p, "1/2")
        b, _ = self.shard(p, "2/2")
        mm = ("--min-plants", "4")
        rep_b = json.loads((b / "report.json").read_text())

        other = dict(rep_b, plants_sha256="f" * 64)
        (b / "report.json").write_text(json.dumps(other))
        rc, log = self.union(p, a, b, extra=mm)
        self.assertEqual(rc, 1, log)

        head = dict(rep_b, git={"head": "deadbeef", "dirty": False})
        (b / "report.json").write_text(json.dumps(head))
        rc, log = self.union(p, a, b, extra=mm)
        self.assertEqual(rc, 1, log)

        extra_id = dict(rep_b, results=rep_b["results"] + [dict(rep_b["results"][0], id="P9")])
        (b / "report.json").write_text(json.dumps(extra_id))
        rc, log = self.union(p, a, b, extra=mm)
        self.assertEqual(rc, 1, log)

        red = dict(rep_b, baseline="FAILED")
        (b / "report.json").write_text(json.dumps(red))
        rc, log = self.union(p, a, b, extra=mm)
        self.assertEqual(rc, 2, log)

        (b / "report.json").write_text(json.dumps(rep_b))
        self.assertEqual(self.union(p, a, b, extra=mm)[0], 0)


class Planter(Case):
    def test_plant_py_writes_applicable_plants(self):
        out = self.tmp / "auto.json"
        r = subprocess.run([PY, str(SCRIPTS / "plant.py"), "--repo", str(self.repo), "--out", str(out), "calc.py"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = json.loads(out.read_text())
        self.assertEqual(doc["mode"], "behavior")
        self.assertGreaterEqual(len(doc["plants"]), 4)
        for p in doc["plants"]:
            e = p["edits"][0]
            self.assertEqual(e["file_sha256"], self.orig)
            self.assertEqual(CALC[e["start"]:e["end"]], e["old"])
        rc, rep, _, log = self.prove(out, "--min-plants", "1")
        self.assertEqual((rc, rep["verdict"]), (0, "PASS"), log)
        self.assert_clean()

    def planter(self, *files, extra=()):
        out = self.tmp / f"auto{self.n}.json"
        self.n += 1
        r = subprocess.run([PY, str(SCRIPTS / "plant.py"), "--repo", str(self.repo), "--out", str(out),
                            *extra, *files], capture_output=True, text=True)
        return r, (json.loads(out.read_text()) if out.exists() else None)

    def test_angle_brackets_of_types_and_tags_are_not_planted_comparisons_are(self):
        # oss-check 2026-11-04: defu src/defu.ts:12 `Record<string, any>` got '<' -> '<=' and '>' -> '>=' plants that
        # only break compilation, so their "kills" tested nothing.
        ts = ("for (const key of Object.keys(baseObject as Record<string, any>)) {}\n"
              "const m: Map<string, Array<number>> = new Map();\n"
              "function pick<T extends object>(x: T): Promise<T> { return x; }\n"
              "const cast = <string>raw;\n"
              "if (a < b && c > d) { go(); }\n"
              "for (let i = 0; i<n; i++) {}\n"
              "if (a<b && c>d) {}\n")
        tsx = "const el = <div className=\"a\" onClick={() => f(p > q)}>{u < v}</div>;\n"
        (self.repo / "t.ts").write_text(ts)
        (self.repo / "v.tsx").write_text(tsx)
        r, doc = self.planter("t.ts", "v.tsx")
        self.assertEqual(r.returncode, 0, r.stderr)
        got = {(e["file"], e["start"]) for p in doc["plants"] for e in p["edits"] if e["old"] in ("<", ">")}
        src = {"t.ts": ts, "v.tsx": tsx}

        def at(file, line_text, token, nth=0):
            text = src[file]
            base = text.index(line_text)
            pos = -1
            for _ in range(nth + 1):
                pos = text.index(token, pos + 1 if pos >= 0 else base)
            return (file, pos)

        brackets = [at("t.ts", "Record<", "<"), at("t.ts", "Record<", ">"), at("t.ts", "Map<", "<"),
                    at("t.ts", "Map<", "<", 1), at("t.ts", "Map<", ">"), at("t.ts", "Map<", ">", 1),
                    at("t.ts", "pick<", "<"), at("t.ts", "Promise<", "<"), at("t.ts", "<string>", "<"),
                    at("t.ts", "<string>", ">"), at("v.tsx", "<div", "<"), at("v.tsx", "</div>", "<")]
        for b in brackets:
            self.assertNotIn(b, got, f"a bracket was planted as a comparison: {b} {src[b[0]][b[1] - 12:b[1] + 3]!r}")
        comparisons = [at("t.ts", "a < b", "<"), at("t.ts", "c > d", ">"), at("t.ts", "i<n", "<"),
                       at("t.ts", "a<b && c>d", "<"), at("t.ts", "c>d", ">"), at("v.tsx", "p > q", ">"),
                       at("v.tsx", "u < v", "<")]
        for c in comparisons:
            self.assertIn(c, got, f"a real comparison was not planted: {c}")

    def test_a_sample_never_hides_a_form_behind_n_a(self):
        r, full = self.planter("calc.py")
        forms = {p["form"] for p in full["plants"]}
        self.assertGreaterEqual(len(forms), 2)
        r, small = self.planter("calc.py", extra=("--max", "1", "--seed", "7"))
        self.assertEqual(r.returncode, 0, r.stderr)
        na = {c["form"] for c in small["coverage"]}
        self.assertFalse(forms & na, f"forms present in the code were marked n/a: {forms & na}")
        self.assertEqual({p["form"] for p in small["plants"]}, forms, "one plant per present form is kept")

    def test_non_utf8_file_is_skipped_not_a_crash(self):
        (self.repo / "latin.py").write_bytes(b"# caf\xe9\nX = 1 + 2\n")
        r, doc = self.planter("latin.py", "calc.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("not UTF-8", r.stderr)
        self.assertTrue(all(p["edits"][0]["file"] == "calc.py" for p in doc["plants"]))


if __name__ == "__main__":
    unittest.main()
