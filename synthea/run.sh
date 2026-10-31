#!/usr/bin/env bash
# Generate ~2,000 living synthetic patients in Chicago, IL (fixed seed) and copy CSVs to data/raw/.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
JAR="$HERE/synthea-with-dependencies.jar"
JAR_URL="https://github.com/synthetichealth/synthea/releases/download/master-branch-latest/synthea-with-dependencies.jar"
JAVA="${JAVA:-$(/usr/libexec/java_home -v 17)/bin/java}"

# Synthea simulates up to "now", so a rerun produces a different population. Keep existing data
# unless explicitly asked to regenerate.
if [ -f "$ROOT/data/raw/patients.csv" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "data/raw/ already has Synthea output; skipping. Run 'make data FORCE=1' to regenerate"
  echo "(note: regenerating produces a different population, so every downstream number changes)."
  exit 0
fi

if [ ! -f "$JAR" ]; then
  echo "Downloading Synthea jar..."
  curl -fL -o "$JAR" "$JAR_URL"
fi

cd "$HERE"
rm -rf output
"$JAVA" -jar "$JAR" -s 42 -p 2000 \
  --exporter.csv.export true \
  --exporter.fhir.export false \
  Illinois Chicago

mkdir -p "$ROOT/data/raw"
cp output/csv/*.csv "$ROOT/data/raw/"
echo "Copied $(ls "$ROOT/data/raw" | wc -l | tr -d ' ') CSV files to data/raw/"
