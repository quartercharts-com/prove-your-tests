#!/usr/bin/env bash
# Light field test on three small public repos: Python + pytest, JS + vitest, JS + mocha with a narrow test.
# Clones into a temp dir, makes behavior plants (at most 10 per repo), proves them, prints one line per repo.
# Usage: tools/oss_check.sh <reports dir>      (needs python3, git, node, npm; network for clones and installs)
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: $0 <reports dir>" >&2; exit 2; }
here="$(cd "$(dirname "$0")/.." && pwd)"
pyt="${PYT:-python3 -I $here/skill/prove-your-tests/scripts/cli.py}"
reports="$(mkdir -p "$1" && cd "$1" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

prove_one() {  # name, test command, files...
  local name="$1" cmd="$2"; shift 2
  local repo="$work/$name"
  printf '*.egg-info/\nnode_modules/\n.venv/\n__pycache__/\n' >> "$repo/.git/info/exclude"  # installs are not user work
  $pyt plant --repo "$repo" --out "$work/$name.json" --max 10 --seed 1 "$@" || { echo "$name: no plants" | tee -a "$reports/summary.txt"; return; }
  local rc=0
  $pyt prove --repo "$repo" --plants "$work/$name.json" --test-cmd "$cmd" --out "$work/out-$name" \
      --timeout 120 --min-plants 1 > "$reports/$name.log" 2>&1 || rc=$?
  cp "$work/out-$name/REPORT.md" "$reports/$name.md" 2>/dev/null || true
  local clean="clean"
  [ -z "$(git -C "$repo" status --porcelain --untracked-files=no)" ] || clean="NOT CLEAN"
  echo "$name: exit $rc, $(tail -1 "$reports/$name.log"), tree after: $clean" | tee -a "$reports/summary.txt"
}

git clone -q --depth 1 https://github.com/pallets/itsdangerous "$work/itsdangerous"
python3 -m venv "$work/venv" && "$work/venv/bin/pip" install -q -e "$work/itsdangerous" pytest freezegun
prove_one itsdangerous "$work/venv/bin/python -m pytest -q -x tests" src/itsdangerous/encoding.py

git clone -q --depth 1 https://github.com/unjs/defu "$work/defu"
(cd "$work/defu" && npx -y pnpm@10 install --silent)
prove_one defu "npx vitest run" src/defu.ts

git clone -q --depth 1 https://github.com/jonschlinkert/is-number "$work/is-number"
(cd "$work/is-number" && npm install --silent --no-audit --no-fund --no-save mocha@10)
prove_one is-number "npx mocha -g 'should return true'" index.js   # a deliberately narrow (weak) test command
