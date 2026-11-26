#!/bin/sh
# Build-time demo data (synthetic invoices). Uses the real Comtrade reference table if committed;
# records which table was used in data/demo/REFERENCE so start.sh analyses with the same one.
set -e
if [ -f data/reference_comtrade.csv ] && \
   kashf generate --seed 7 --n 6000 --out data/demo --reference data/reference_comtrade.csv; then
  echo "data/reference_comtrade.csv" > data/demo/REFERENCE
  echo "demo: synthetic invoices priced around real UN Comtrade medians"
else
  kashf generate --seed 7 --n 6000 --out data/demo
  echo "illustrative" > data/demo/REFERENCE
  echo "demo: synthetic invoices, illustrative reference prices"
fi
