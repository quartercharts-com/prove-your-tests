# Gemini CLI context (GEMINI.md)

This project uses **prove-your-tests** (https://github.com/quartercharts-com/prove-your-tests), a deterministic
CLI that proves a test suite catches real bugs. Install it with `pipx install git+https://github.com/quartercharts-com/prove-your-tests`
(or `uv tool install` with the same URL).
The verdict always comes from the CLI, never from you.

When asked to prove, check or mutation-test some tests:
1. Make sure the work tree is committed (the CLI refuses uncommitted changes; `--allow-dirty` overrides).
2. Baseline: the narrow test command for the code must be green.
3. Guard mode: `prove-your-tests scan --repo . --name <guarded name>` lists the real call forms.
4. Plants: `prove-your-tests plant --repo . --out plants.json <files>` for Python or JS/TS behavior plants.
   For guard (escape) plants, or any other language, write them yourself by following the plant-writer
   prompt that `prove-your-tests prompt` prints, and NEVER read the test files while you write plants. Then `prove-your-tests check-plants plants.json --repo .`
   must say valid. Commit the plants before you touch any test.
5. Run: `prove-your-tests prove --repo . --plants plants.json --test-cmd "<narrow test command>" --out .prove-out/<label>`.
6. Read `.prove-out/<label>/REPORT.md`. Exit 0 PASS, 1 FAIL (survivors), 2 NOT-RUN (never report it as
   PASS), 3 a file was not restored: run `prove-your-tests recover .prove-out/<label>` at once.
7. For each SURVIVED plant, write the missing test (check effects for money, accounts and access; write
   business numbers into the test, never the code's own constant). Re-run on the SAME plants file. Never
   delete or soften a plant to get a PASS.

Full steps and the catalog of bug forms: https://github.com/quartercharts-com/prove-your-tests
