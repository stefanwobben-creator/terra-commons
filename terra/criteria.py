"""De acht criteria, ingedeeld naar wat ze werkelijk zijn.

Toets (model paragraaf 13): filtert dit op een eigenschap van het perceel, of op een
keuze die wij nog kunnen maken? Alleen het eerste is een poort.

  gate   -> afwijzen. Eigenschap van grond of titel, niet met geld op te lossen.
  cond   -> voorwaarde. Bindt alleen bij een bepaalde beheerintentie of plan.
  score  -> kosten of tijdelijk risico. Hoort in de score, niet in de poort.
"""
from dataclasses import dataclass
from typing import Literal, Optional

Category = Literal["gate", "cond", "score"]
Intent = Literal["dehesa", "rewild"]


@dataclass(frozen=True)
class Criterion:
    k: str
    category: Category
    scope: str
    label: str
    jurisdiction: Optional[str] = None
    intent_dep: bool = False
    testable_from_listing: bool = False


CRITERIA = (
    Criterion("K1", "cond",  "municipality", "neerslag onder de ondergrens", intent_dep=True),
    Criterion("K2", "cond",  "parcel", "boven 100 ha beweidbaar",
              jurisdiction="ES-EX", intent_dep=True, testable_from_listing=True),
    Criterion("K3", "score", "parcel", "onder tweemaal de kaveleenheid",
              testable_from_listing=True),
    Criterion("K4", "gate",  "parcel", "geen juridisch verzekerde toegang"),
    Criterion("K5", "gate",  "parcel", "niet in het eigendomsregister"),
    Criterion("K6", "gate",  "parcel", "via pecuaria eroverheen"),
    Criterion("K7", "cond",  "municipality", "grondwatervoorraad en riesgo"),
    Criterion("K8", "score", "parcel", "boven 400 ha, brandpreventieplan",
              testable_from_listing=True),
)

GATES = tuple(c for c in CRITERIA if c.category == "gate")
BY_K = {c.k: c for c in CRITERIA}

RAIN_FLOOR_MM = {"dehesa": 450, "rewild": 500}
PROFILE_HA = (20, 90)
MIN_HA_FALLBACK = 16
