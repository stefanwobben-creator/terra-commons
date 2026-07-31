#!/usr/bin/env bash
# Zet de database op vanaf nul en schrijf site/data.json. Idempotent.
set -euo pipefail
: "${DATABASE_URL:?zet DATABASE_URL}"
# Alles wat in sql/ staat, op nummervolgorde. Bewust geen handmatige lijst meer:
# die stond op 001 tot 003 terwijl er inmiddels 004 tot 008 bij waren gekomen, en
# dus draaide de runner een schema van vijf bestanden geleden. Dat viel niet op
# omdat de fout pas een stap later viel, bij het inladen van de seed.
# Elk nieuw SQL-bestand doet vanaf nu vanzelf mee.
shopt -s nullglob
bestanden=(sql/*.sql)
if [ ${#bestanden[@]} -eq 0 ]; then
  echo "geen sql-bestanden gevonden; klopt de werkmap?" >&2
  exit 1
fi
for f in "${bestanden[@]}"; do
  echo "== $f"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f "$f"
done
python -m terra.load_seed
python -m terra.nightly
python -m terra.export
