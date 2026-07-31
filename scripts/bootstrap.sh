#!/usr/bin/env bash
# Zet de database op vanaf nul en schrijf site/data.json. Idempotent.
set -euo pipefail
: "${DATABASE_URL:?zet DATABASE_URL}"
for f in sql/001_schema.sql sql/002_views.sql sql/003_constraints.sql; do
  echo "== $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done
python -m terra.load_seed
python -m terra.nightly
python -m terra.export
