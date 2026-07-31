"""Configuratie op een plek. Alles via omgeving, zodat lokaal en Render hetzelfde
codepad volgen en er geen 'werkt-alleen-op-mijn-machine' pad ontstaat."""
from __future__ import annotations

import os

# Render zet DATABASE_URL zelf. Lokaal valt hij terug op de sessiedatabase.
DSN = os.environ.get(
    "DATABASE_URL",
    "postgresql://terra:terra@127.0.0.1:5432/terra",
)

# Rijpheidspoort: betrouwbaar / vergelijkbaar / volledig, in procenten.
# Deze drie staan ook in sql/002_views.sql. Bij wijziging: beide aanpassen,
# tests/test_pipeline.py vergelijkt ze met elkaar en klapt eruit als ze uiteenlopen.
THRESHOLDS = (80, 100, 95)

# Zoekprofiel. Niet hard: MIN_HA_FALLBACK is de wettelijke ondergrens,
# PROFILE_HA is wat de groep wil.
PROFILE_HA = (20, 90)

DRY_RUN = os.environ.get("TERRA_DRY_RUN", "0") == "1"

# Elke advertentie moet een URL en een kijkdatum hebben. Zonder dat is een
# vermelding niet na te lopen, en dan is de hele herkomstadministratie theater.
REQUIRE_LISTING_URL = os.environ.get("TERRA_REQUIRE_URL", "1") == "1"
