# Contributing

Thanks for helping. Two rules keep this tool honest, and every change must keep them:

1. **The verdict is a script, never a model.** Nothing that decides PASS, FAIL or NOT-RUN may call a model or
   read model output.
2. **NOT-RUN is never PASS.** Anything that was not run, not killed, not restored byte-identical, or not
   controlled must stay out of PASS.

## Before you open a pull request

```bash
python3 tests/test_prover.py            # the self-test, about 1 minute, stdlib only
bash examples/shop/run_demo.sh /tmp/demo # the worked example; the four verdicts must not change
```

- A change to `prove.py` or `union.py` needs a self-test case that is red without the change.
- Behavior the self-test does not cover yet: add a case first, then the change.
- `tests/plants/prover.json` holds plants that would make the runner lie. They are written by a separate plant
  writer that never reads the self-test. Do not edit a plant to make it pass; if your change moves the code a
  plant targets, say so in the pull request and a maintainer re-anchors it with a separate writer.
- Python 3.9 or newer, standard library only, for everything under `skill/`.

## Style

Plain words in messages and docs. Report numbers as measured, with the command that produced them.
