#!/usr/bin/env bash
# Pull real UN Comtrade data and produce every real-data result in one go.
#
#   1. put your key in .env at the repo root:   COMTRADE_KEY=...
#   2. bash scripts/run_real.sh
#
# Uses about 16 API calls (free tier: 500/day). Re-running is free: responses are cached in data/raw/.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! git check-ignore -q .env; then
  echo "STOP: .env is not ignored by git; refusing to continue (your key would be committed)." >&2
  exit 1
fi
[ -f .env ] || { echo "STOP: create .env with COMTRADE_KEY=<your key> first (see .env.example)." >&2; exit 1; }

echo "== 1/6 test call (UAE, HS 851713, 2023)"
python -m kashf.comtrade test

echo "== 2/6 pull UAE + partner mirror + world flows (cached in data/raw/)"
python -m kashf.comtrade pull

echo "== 3/6 real reference price table -> data/reference_comtrade.csv"
python -m kashf.comtrade reference --allow-partial

echo "== 4/6 data card -> docs/DATA_CARD.md"
python -m kashf.comtrade card

echo "== 5/6 macro layer on real mirror data -> results/macro/"
python -m kashf.macro --out results/macro

echo "== 6/6 invoice layer with the real reference table -> results/real_reference/"
python -m kashf.evaluate --seeds 5 --reference data/reference_comtrade.csv --out results/real_reference

echo
echo "Done. Read results/macro/macro_results.md (real data) and results/real_reference/results.md."
