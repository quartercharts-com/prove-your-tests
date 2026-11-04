---
name: prove-your-tests
description: Proves that a test suite or a guard test really catches bugs, instead of trusting that it does. Plants deliberate bugs (written by a separate plant-writer that never reads the tests), runs the tests against each one, and says PASS only when every plant turned the tests red, every file came back byte-identical and the tests went green again. Use when the user types /prove-your-tests, or asks "do my tests catch anything", "prove these tests", "mutation test this", "is this guard real", "would this test catch a bypass", or before trusting a test that protects money, accounts or access.
---

# Prove your tests

A green test proves only that the test ran. This skill proves it would turn red on a real bug.

**The loop:** scan the real call forms, have a separate plant writer write at least 25 plants, run every
plant (red), restore it (byte-identical), run again (green), and turn every surviving plant into a new test.

```
code --scan_forms.py--> real call forms --plant-writer (never reads tests)--> plants.json
plants.json --prove.py--> per plant: apply, tests RED?, restore, bytes identical?, tests GREEN?
                       --> REPORT.md: PASS | FAIL (survivors) | NOT-RUN (anything not proven)
```

## Words
- **Plant**: one small deliberate bug, as an exact text edit or a new file. `plants.json` holds them.
- **KILLED**: the tests failed with the plant in place. Good. **SURVIVED**: they still passed. A hole.
- **Negative control**: after the restore the same tests must pass again; otherwise the kill proves nothing.
- **Behavior plants** (M1 to M9) change existing lines. **Escape plants** (E1 to E15) add code that
  reaches the forbidden effect in a sneaky form. See `references/catalog.md`.

## Steps

1. **Pick the target and the rule.** Which tests or which guard, which code they protect, and the rule in
   one sentence ("only `refund()` moves money"). Choose the mode: `behavior` (do the tests notice a changed
   line?) or `guard` (does the guard notice a bypass?). Money, accounts and access deserve both.
2. **Baseline.** Commit your work first: the runner refuses uncommitted changes or a folder that is not a
   git work tree (`--allow-dirty` overrides), so `git status` can always show what a crash left. The test
   command must be green on the untouched tree 3 times in a row (`--baseline-runs`), or nothing else means
   anything; a red run among them means flaky tests (NOT-RUN). Keep it narrow: the test files for this code,
   not the whole suite.
3. **Scan the real call forms** (guard mode):
   `python3 -I scripts/scan_forms.py --repo <repo> --name <guarded name> [--name ...]`
   Tests are skipped by the scan on purpose.
4. **Write the plants with a separate writer.** Never write them in the window that wrote the tests.
   - Behavior mode, Python or JS/TS: `python3 -I scripts/plant.py --repo <repo> --out plants.json <files>`
     (`--lines file:10-40` for only the changed lines, `--max N --seed S` to sample a big file).
   - Guard mode, or any language `plant.py` does not read: launch the `plant-writer` agent
     (`agents/plant-writer.md`; installed with the plugin, or copy it to `~/.claude/agents/`) with the repo,
     the files it may plant in, the rule, the guarded names, the output path, the mode and the minimum. Any
     other AI can write plants from the same prompt (`prompts/plant-writer.md`, or `prove-your-tests prompt`).
   - Check any writer's answer before using it: `python3 -I scripts/plants_schema.py plants.json --repo <repo>`
     (`prove-your-tests check-plants`). A malformed or partial plants file is refused; it is never run. Default model
     and effort come from `config.default.json` (strongest model, high effort); override per repo with
     `.prove-your-tests.json`.
   - **Models and effort:** the strongest model at high effort writes the plants and fixes the tests;
     a script (no model) runs them. On a small plan a cheaper model (`small_plan_model`) may write the
     simple, repetitive plants; keep the strongest one for escape plants on money, accounts and sign-up.
   - Commit the plants file BEFORE you touch the tests. The commit order is the proof that the plants
     were not fitted to the tests.
5. **Run the proof** (a script, no model):
   `python3 -I scripts/prove.py --repo <repo> --plants plants.json --test-cmd "<narrow test command>" --out .prove-out/<label>`
   - At least 25 plants (`--min-plants`), every catalog form planted or `n/a` with a reason.
   - `--timeout` per run. A hang is TIMEOUT, which is NOT-RUN: a hang never counts as a kill.
   - After each kill the tests run again without the plant (the control). A red control is run once more:
     red then green is FLAKY (not counted as a kill, NOT-RUN); red twice is FAIL.
   - Big corpora: shard with `--shard 1/4` ... `--shard 4/4` (in CI or on separate machines), then
     `python3 -I scripts/union.py --plants plants.json <out dirs>`. The union fails on a missing, extra or
     duplicate plant, or on shards that ran a different plants file or repo head.
   - Crash or kill mid-run: `prove.py --recover <out dir>` puts every file back from the journal. A new
     run refuses to start while a journal exists.
6. **Read the verdict** in `REPORT.md` and `report.json` in the out dir.
   - **PASS** (exit 0): every plant ran, was killed, restored byte-identical, control green, enough
     plants, every form covered.
   - **FAIL** (exit 1): a plant survived, a restore failed, a control went red, or the plan and the run
     differ. Exit 3 means a file was not restored: run `--recover` first.
   - **NOT-RUN** (exit 2): baseline red or flaky, a stale plant (its file changed, is not UTF-8, or the plant
     changes nothing), a plant that could not be applied (read-only file, disk full), a timeout, a flaky
     control, too few plants, a form with no plant and no reason, an interrupted or partial run, a refused
     plants file or a dirty tree. Never report it as PASS.
7. **Fix the holes, not the plants.** For each survivor write the missing test (the report shows the plant
   and the test output). Rules that keep the new tests honest:
   - Money, accounts, access: check the EFFECT (no ledger row, no account row, no write, no 2xx), not a
     name or a text pattern.
   - Write business numbers into the test (`refund(order, 51)` must fail), never `shop.MAX + 1`: a test
     that reads the code's own constant moves with it.
   - Then re-run step 5 on the SAME plants file. Never delete or soften a plant to get a PASS.
8. **Report** in this shape:
   ```
   PROVE YOUR TESTS: PASS 25/25 killed, 0 survived, 0 not run
   CATALOG: guard 15/15 forms (n/a: E12 no routes)
   PLANT AUTHOR: plant-writer (tests not read), plants commit <sha>
   TESTS: <test command>, repo head <sha>
   ```

## Where to run it
Each plant is a full test run, twice (red, then the control). Small corpora run anywhere. Big ones belong
in CI: shard across jobs, keep the plants file and the head identical, and join with `union.py`. Never run
a corpus against a real database, a real payment provider or production.

## Files
- `scripts/plant.py`: behavior plants for Python (AST) and JS/TS (token rules).
- `scripts/scan_forms.py`: the repo's real call forms of the guarded names, tests skipped.
- `scripts/prove.py`: the runner; journal, restore, control, verdict, `--recover`, `--shard`.
- `scripts/union.py`: one verdict from shard reports.
- `scripts/plants_schema.py`: checks a plants file from any writer before it runs.
- `scripts/cli.py`: the `prove-your-tests` command (all of the above as subcommands).
- `scripts/mcp_server.py`: the same commands as MCP tools, for any MCP client.
- `scripts/write_plants.py`: optional headless plant writer for CI (Anthropic or any OpenAI-compatible API;
  key from an environment variable only).
- `prompts/plant-writer.md`: the plant-writer prompt, the same for every model.
- `references/catalog.md`: forms M1 to M9 and E1 to E15, and how to plant well.
- `config.default.json`: models, effort, minimum plants, timeout, control. All defaults, all changeable.
