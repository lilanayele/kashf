#!/bin/sh
# Start the dashboard on $PORT (Render sets it; 8800 locally), bound to all interfaces.
set -e
REF=""
if [ "$(cat data/demo/REFERENCE 2>/dev/null)" = "data/reference_comtrade.csv" ]; then
  REF="--reference data/reference_comtrade.csv"
fi
MACRO=""
[ -f results/macro/flags.csv ] && MACRO="--macro-dir results/macro"
exec kashf serve data/demo --host 0.0.0.0 --port "${PORT:-8800}" $REF $MACRO
