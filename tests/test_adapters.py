"""Self-test for everything around the runner: the plants validator, the CLI, the MCP server, the headless plant
writer (against a local fake model server: no network, no key, no cost) and the adapter files.

Every case runs in its own temporary folder, never in this repo.
"""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skill" / "prove-your-tests"
SCRIPTS = SKILL / "scripts"
PY = sys.executable
CALC = "def is_adult(age):\n    return age >= 18\n"
TEST = ("import unittest\nimport calc\n\n\nclass T(unittest.TestCase):\n    def test(self):\n"
        "        self.assertTrue(calc.is_adult(18))\n        self.assertFalse(calc.is_adult(17))\n")
FAKE_KEY = "sk-fake-" + "0123456789abcdef" * 2


def good_plants(n=2):
    return {"version": 1, "mode": "behavior",
            "plants": [{"id": f"P{i}", "form": "M1", "author": "fake model", "why": "w",
                        "edits": [{"file": "calc.py", "old": "age >= 18", "new": f"age >= {18 + i}"}]}
                       for i in range(1, n + 1)],
            "coverage": [{"form": f"M{i}", "na": "tiny file"} for i in range(2, 10)]}


def run(*args, inp=None, env=None, cwd=None):
    r = subprocess.run([PY, "-I", *map(str, args)], capture_output=True, text=True, input=inp,
                       env={**os.environ, **(env or {})}, cwd=cwd, timeout=120)
    return r.returncode, r.stdout + r.stderr


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pyt-adapters-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        (self.repo / "calc.py").write_text(CALC)
        (self.repo / "test_calc.py").write_text(TEST)
        g = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
        subprocess.run([*g[:1], "init", "-q"], cwd=self.repo)
        subprocess.run([*g, "add", "-A"], cwd=self.repo)
        subprocess.run([*g, "commit", "-qm", "i"], cwd=self.repo)

    def write(self, name, obj):
        p = self.tmp / name
        p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
        return p


class Validator(Base):
    def test_bad_json_is_not_run_not_a_crash(self):
        p = self.write("p.json", "{not json")
        rc, log = run(SCRIPTS / "prove.py", "--repo", self.repo, "--plants", p, "--test-cmd", "true",
                      "--out", self.tmp / "o")
        self.assertEqual(rc, 2, log)
        self.assertIn("not valid JSON", log)
        self.assertNotIn("Traceback", log)

    def test_partial_model_answer_lists_every_problem(self):
        doc = {"mode": "behavior", "plants": [{"id": "A", "form": "M1"}, {"id": "A", "form": "Z9", "edits": [{}]}]}
        rc, log = run(SCRIPTS / "plants_schema.py", self.write("p.json", doc))
        self.assertEqual(rc, 2, log)
        for want in ("edits must be a non-empty list", "duplicate id A", "form must be one of", "file must be"):
            self.assertIn(want, log)

    def test_repo_check_reports_plants_that_do_not_apply(self):
        doc = good_plants()
        doc["plants"][0]["edits"][0]["old"] = "not in the file"
        rc, log = run(SCRIPTS / "plants_schema.py", self.write("p.json", doc), "--repo", self.repo)
        self.assertEqual(rc, 2, log)
        self.assertIn("plant P1", log)


class Insertion(Base):
    def test_positional_insertion_with_empty_old_is_valid_and_proves(self):
        # plant.py writes M9 "reraise" plants as an insertion: old "" at start == end (found on a real repo)
        at = CALC.index("return")
        doc = good_plants(1)
        doc["plants"].append({"id": "INS", "form": "M9", "edits": [{"file": "calc.py", "start": at, "end": at,
                                                                  "old": "", "new": "raise ValueError\n    "}]})
        p = self.write("p.json", doc)
        rc, log = run(SCRIPTS / "plants_schema.py", p, "--repo", self.repo)
        self.assertEqual(rc, 0, log)
        out = self.tmp / "o"
        rc, log = run(SCRIPTS / "prove.py", "--repo", self.repo, "--plants", p, "--test-cmd",
                      f"{PY} -m unittest -q test_calc", "--out", out, "--min-plants", "2")
        self.assertEqual(rc, 0, log)
        self.assertEqual((self.repo / "calc.py").read_text(), CALC)

    def test_empty_old_without_a_position_is_refused(self):
        doc = good_plants(1)
        doc["plants"][0]["edits"][0]["old"] = ""
        rc, log = run(SCRIPTS / "plants_schema.py", self.write("p.json", doc))
        self.assertEqual(rc, 2, log)
        self.assertIn("insertion at a fixed position", log)


class Cli(Base):
    def test_every_command_is_wired(self):
        rc, log = run(SCRIPTS / "cli.py", "--help")
        self.assertEqual(rc, 0, log)
        for cmd in ("prove", "recover", "plant", "scan", "check-plants", "union", "write-plants", "mcp", "prompt"):
            self.assertIn(cmd, log)
        rc, log = run(SCRIPTS / "cli.py", "check-plants", self.write("p.json", good_plants()))
        self.assertEqual(rc, 0, log)
        rc, log = run(SCRIPTS / "cli.py", "nope")
        self.assertEqual(rc, 2, log)

    def test_prove_through_the_cli(self):
        out = self.tmp / "o"
        rc, log = run(SCRIPTS / "cli.py", "prove", "--repo", self.repo, "--plants", self.write("p.json", good_plants()),
                      "--test-cmd", f"{PY} -m unittest -q test_calc", "--out", out, "--min-plants", "2")
        self.assertEqual(rc, 0, log)
        self.assertEqual(json.loads((out / "report.json").read_text())["verdict"], "PASS")

    def test_prompt_and_claude_agent_are_one_text(self):
        prompt = (SKILL / "prompts" / "plant-writer.md").read_text()
        agent = (ROOT / "agents" / "plant-writer.md").read_text()
        self.assertTrue(agent.startswith("---\nname: plant-writer\n"))
        self.assertEqual(agent.split("---\n", 2)[2].lstrip("\n"), prompt, "agents/plant-writer.md drifted from the prompt")
        rc, log = run(SCRIPTS / "cli.py", "prompt")
        self.assertEqual((rc, log), (0, prompt))


class Mcp(Base):
    def talk(self, *msgs):
        inp = "".join(json.dumps(m) + "\n" for m in msgs)
        rc, out = run(SCRIPTS / "mcp_server.py", inp=inp)
        self.assertEqual(rc, 0, out)
        return [json.loads(line) for line in out.splitlines() if line.strip()]

    def test_initialize_list_and_call(self):
        plants = self.write("p.json", good_plants())
        replies = self.talk(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "prove", "arguments": {"repo": str(self.repo), "plants": str(plants),
                                                       "test_cmd": f"{PY} -m unittest -q test_calc",
                                                       "out": str(self.tmp / "o"), "min_plants": 2}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "prove", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 5, "method": "nope"})
        self.assertEqual([r["id"] for r in replies], [1, 2, 3, 4, 5], "a notification gets no answer")
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "prove-your-tests")
        names = {t["name"] for t in replies[1]["result"]["tools"]}
        self.assertEqual(names, {"check_plants", "scan_forms", "plant", "prove", "recover", "union"})
        call = replies[2]["result"]
        self.assertFalse(call["isError"])
        self.assertIn("prove: PASS", call["content"][0]["text"])
        self.assertTrue(replies[3]["result"]["isError"])
        self.assertEqual(replies[4]["error"]["code"], -32601)


class FakeModel(http.server.BaseHTTPRequestHandler):
    answer = ""
    seen: list = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        FakeModel.seen.append({"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        if "anthropic-version" in self.headers:
            data = {"content": [{"type": "text", "text": FakeModel.answer}]}
        else:
            data = {"choices": [{"message": {"content": FakeModel.answer}}]}
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class Headless(Base):
    def setUp(self):
        super().setUp()
        self.server = http.server.HTTPServer(("127.0.0.1", 0), FakeModel)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        FakeModel.seen = []

    def tearDown(self):
        self.server.shutdown()

    def write_plants(self, provider, answer, *extra, key=FAKE_KEY, files=("calc.py",)):
        FakeModel.answer = answer
        env = {"PYT_TEST_KEY": key} if key else {"PYT_TEST_KEY": ""}
        return run(SCRIPTS / "write_plants.py", "--provider", provider, "--model", "fake-1", "--repo", self.repo,
                   "--mode", "behavior", "--rule", "adults are 18 or older", "--out", self.tmp / "out.json",
                   "--base-url", self.url, "--key-env", "PYT_TEST_KEY", "--min-plants", "2", *extra, *files, env=env)

    def test_openai_compatible_good_answer_is_written_and_proves(self):
        rc, log = self.write_plants("openai", "Here you go:\n```json\n" + json.dumps(good_plants()) + "\n```")
        self.assertEqual(rc, 0, log)
        doc = json.loads((self.tmp / "out.json").read_text())
        self.assertEqual(len(doc["plants"]), 2)
        self.assertIn("plants_sha256", doc)
        sent = FakeModel.seen[0]
        self.assertEqual(sent["headers"]["authorization"], f"Bearer {FAKE_KEY}")
        prompt = sent["body"]["messages"][0]["content"]
        self.assertIn("def is_adult", prompt)
        self.assertNotIn("class T(unittest.TestCase)", prompt, "the model must never see a test file")
        self.assertNotIn(FAKE_KEY, log)

    def test_anthropic_answer(self):
        rc, log = self.write_plants("anthropic", json.dumps(good_plants()))
        self.assertEqual(rc, 0, log)
        self.assertEqual(FakeModel.seen[0]["headers"]["x-api-key"], FAKE_KEY)

    def test_bad_answers_are_not_run_and_write_nothing(self):
        stale = good_plants()
        stale["plants"][0]["edits"][0]["old"] = "age > 99"
        other_file = good_plants()
        other_file["plants"][0]["edits"][0]["file"] = "test_calc.py"
        echoes_key = good_plants()
        echoes_key["plants"][0]["form"] = FAKE_KEY  # a model that echoes the key into an error message
        for answer in ("no json at all", json.dumps({"mode": "behavior", "plants": []}), json.dumps(stale),
                       json.dumps(good_plants(1)), json.dumps(dict(good_plants(), mode="guard")), json.dumps(other_file),
                       json.dumps(echoes_key)):
            rc, log = self.write_plants("openai", answer)
            self.assertEqual(rc, 2, f"{answer[:60]} -> {log}")
            self.assertFalse((self.tmp / "out.json").exists(), "a bad answer must write no file")
            self.assertNotIn(FAKE_KEY, log)

    def test_no_key_and_test_files_are_refused_before_any_call(self):
        rc, log = self.write_plants("openai", json.dumps(good_plants()), key=None)
        self.assertEqual(rc, 2, log)
        self.assertIn("PYT_TEST_KEY", log)
        rc, log = self.write_plants("openai", json.dumps(good_plants()), files=("test_calc.py",))
        self.assertEqual(rc, 2, log)
        self.assertEqual(FakeModel.seen, [], "nothing may be sent when the input is refused")

    def test_provider_error_never_shows_the_key(self):
        FakeModel.answer = ""
        rc, log = run(SCRIPTS / "write_plants.py", "--provider", "openai", "--model", "m", "--repo", self.repo,
                      "--mode", "behavior", "--rule", "r", "--out", self.tmp / "o.json",
                      "--base-url", f"http://127.0.0.1:9/{FAKE_KEY}", "--key-env", "PYT_TEST_KEY", "calc.py",
                      env={"PYT_TEST_KEY": FAKE_KEY})
        self.assertEqual(rc, 3, log)
        self.assertNotIn(FAKE_KEY, log)


class AdapterFiles(unittest.TestCase):
    def test_adapters_point_at_the_one_core(self):
        for f in ("adapters/AGENTS.md", "adapters/GEMINI.md", "adapters/cursor/prove-your-tests.mdc"):
            text = (ROOT / f).read_text()
            self.assertIn("prove-your-tests prove", text, f)
            self.assertIn("prove-your-tests prompt", text, f)
        mdc = (ROOT / "adapters/cursor/prove-your-tests.mdc").read_text()
        self.assertTrue(mdc.startswith("---\ndescription:"), "Cursor rules need frontmatter with a description")

    def test_plugin_and_marketplace_manifests(self):
        plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(plugin["name"], "prove-your-tests")
        self.assertEqual(market["plugins"][0]["name"], plugin["name"])
        self.assertEqual(plugin["license"], "MIT")
        for p in plugin["skills"]:
            self.assertTrue(p.startswith("./") and (ROOT / p).is_dir(), p)
        self.assertTrue((ROOT / plugin["skills"][0] / "prove-your-tests" / "SKILL.md").is_file())

    def test_action_script_block_runs_and_sets_outputs(self):
        text = (ROOT / "action.yml").read_text()
        block = text.split("      run: |\n", 1)[1]
        script = "\n".join(line[8:] for line in block.splitlines())
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            repo = t / "repo"
            repo.mkdir()
            (repo / "calc.py").write_text(CALC)
            (repo / "test_calc.py").write_text(TEST)
            g = ["git", "-c", "user.email=t@example.invalid", "-c", "user.name=t"]
            subprocess.run(["git", "init", "-q"], cwd=repo)
            subprocess.run([*g, "add", "-A"], cwd=repo)
            subprocess.run([*g, "commit", "-qm", "i"], cwd=repo)
            (t / "p.json").write_text(json.dumps(good_plants()))
            env = {**os.environ, "PYT_SCRIPTS": str(SCRIPTS), "PYT_PLANTS": str(t / "p.json"),
                   "PYT_TEST_CMD": f"{PY} -m unittest -q test_calc", "PYT_REPO": str(repo), "PYT_OUT": str(t / "o"),
                   "PYT_TIMEOUT": "60", "PYT_MIN": "2", "PYT_SHARD": "", "GITHUB_OUTPUT": str(t / "gh_out"),
                   "GITHUB_STEP_SUMMARY": str(t / "summary")}
            r = subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("verdict=PASS", (t / "gh_out").read_text())
            self.assertIn("# Prove your tests: PASS", (t / "summary").read_text())
            env["PYT_MIN"] = "25"
            r = subprocess.run(["bash", "-c", script], env={**env, "PYT_OUT": str(t / "o2")}, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("verdict=NOT-RUN", (t / "gh_out").read_text())

    def test_no_internal_names_in_shipped_files(self):
        banned = ["/Users/", "/home/", "C:\\Users"]  # personal paths never ship
        extra = ROOT / "tests" / "internal-names.txt"  # private names, kept only in the development repo
        if extra.is_file():
            banned += [w for w in extra.read_text().splitlines() if w.strip()]
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file() or path.suffix not in {".md", ".py", ".json", ".yml", ".toml", ".mdc", ".sh"}:
                continue
            if path.name in ("test_adapters.py", "internal-names.txt"):
                continue
            text = path.read_text(errors="replace")
            for b in banned:
                self.assertNotIn(b, text, f"{path.relative_to(ROOT)} contains {b!r}")


if __name__ == "__main__":
    unittest.main()
