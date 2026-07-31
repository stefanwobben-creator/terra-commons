#!/usr/bin/env bash
# De periodieke taak. De exit-code is niet cosmetisch: Render markeert de run als
# mislukt, en dat is precies wat je wil zien in plaats van een stille lege nacht.
set -euo pipefail
: "${DATABASE_URL:?zet DATABASE_URL}"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f sql/002_views.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -q -f sql/003_constraints.sql
python -m terra.nightly
python -m terra.export
# site/data.json is nu bijgewerkt in de container van de cronjob, niet in de repo.
# Zolang de site statisch is, is committen en pushen de manier om het zichtbaar te
# maken. Dat is bewust een handmatige stap: een bot die naar main pusht zonder dat
# iemand de uitkomst gezien heeft, is precies het groene vinkje dat we vermijden.
