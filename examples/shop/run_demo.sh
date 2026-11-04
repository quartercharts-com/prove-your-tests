#!/usr/bin/env bash
# Runs the four demo proofs on a COPY of the shop and writes their reports to the folder you name.
# Usage: examples/shop/run_demo.sh <reports dir>
# Set PYT to use an installed command instead of the scripts in this repo, e.g. PYT=prove-your-tests.
set -euo pipefail
[ $# -eq 1 ] || { echo "usage: $0 <reports dir>" >&2; exit 2; }
here="$(cd "$(dirname "$0")" && pwd)"
scripts="$here/../../skill/prove-your-tests/scripts"
pyt="${PYT:-python3 -I $scripts/cli.py}"
reports="$(mkdir -p "$1" && cd "$1" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp -R "$here" "$work/shop"
rm -rf "$work/shop/plants" "$work/shop/runs"
# the prover refuses uncommitted work, so the copy becomes its own small git repo
git -C "$work/shop" init -q
git -C "$work/shop" add -A
git -C "$work/shop" -c user.email=demo@example.invalid -c user.name=demo commit -qm "shop demo copy"

$pyt plant --repo "$work/shop" --out "$work/behavior.json" shop.py
run() {  # label, plants file, test module
  $pyt prove --repo "$work/shop" --plants "$2" \
    --test-cmd "python3 -m unittest -q tests.$3" --out "$work/out-$1" --timeout 60 | tail -1 || true
  sed -e "s#$work#<copy>#g" "$work/out-$1/REPORT.md" > "$reports/$1.md"
}
run weak-tests-vs-code-changes "$work/behavior.json" test_shop_weak
run effect-guard-vs-code-changes "$work/behavior.json" test_guard_effect
run pattern-guard-vs-escapes "$here/plants/escape.json" test_guard_pattern
run effect-guard-vs-escapes "$here/plants/escape.json" test_guard_effect
if diff -r -x __pycache__ -x plants -x runs -x .git "$here" "$work/shop" >/dev/null; then
  echo "demo: the shop copy is byte-identical after every run"
else
  echo "demo: FAILED, the shop copy differs from the original after the runs" >&2
  exit 1
fi
