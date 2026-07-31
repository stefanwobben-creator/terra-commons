"""Laag 1: regio. Een filter, geen aankoop.

Twee dingen die hier gebeuren en die de site niet deed:
1. De landpoort erft door. Een regio in een land met een gesloten poort wordt
   afgewezen, ongeacht de regioscore.
2. Een regio met een ontbrekende component krijgt 'pending' en geen rangnummer.
   Extremadura stond eerste met een leeg brandvak, en dat is geen eerste plaats.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import db, promote
from ..scoring import region_score, tipping_point

SEED = Path(__file__).resolve().parents[2] / "seed"
PASS_PCT = 60          # van het gemeten maximum, niet van 100


def _components() -> dict[str, dict]:
    return json.loads((SEED / "region_scores.json").read_text())["scores"]


def gate_open(c) -> bool:
    r = db.q(c, "select gate_open from v_readiness where tier='region'")
    return bool(r and r[0]["gate_open"])


def run(c, run_id: int | None = None) -> dict:
    comps = _components()
    # De drempel van 60 procent mag pas afwijzen als de invoer rijp is. Een streng
    # filter op dunne data wijst geen regio's af maar meetfouten, en dat is het
    # verschil tussen selectief zoeken en willekeur.
    filtering = gate_open(c)
    rows = db.q(c, """
        select r.code, r.name, r.country_code, co.gate_open, co.gate_reason
        from region r join country co on co.code = r.country_code order by r.code""")
    stats = {"seen": len(rows), "promoted": 0, "rejected": 0, "pending": 0,
             "changed": 0, "filtering": filtering, "scores": {}}
    scored: dict[str, dict] = {}
    for r in rows:
        sc = region_score(comps.get(r["code"], {}))
        scored[r["code"]] = sc
        reasons: list[str] = []
        if r["gate_open"] is False:
            status, reasons = "rejected", [f"landpoort dicht: {r['gate_reason']}"]
        elif r["gate_open"] is None:
            status, reasons = "pending", ["landpoort niet vastgesteld"]
        elif sc["missing"]:
            status = "pending"
            reasons = [f"component {', '.join(sc['missing'])} niet gemeten, "
                       f"score {sc['points']:.0f} van {sc['measured_max']} gemeten punten"]
        elif filtering and sc["pct_of_measured"] < PASS_PCT:
            status = "rejected"
            reasons = [f"{sc['pct_of_measured']}% van het maximum, onder de {PASS_PCT}%"]
        else:
            status = "promoted"
            reasons = [f"{sc['pct_of_measured']}% van het maximum"]
            if not filtering:
                reasons.append("rangschikking, geen selectie: rijpheidspoort dicht")
        stats[status] += 1
        stats["scores"][r["code"]] = {"points": sc["points"], "missing": sc["missing"],
                                      "measured_max": sc["measured_max"],
                                      "pct": sc["pct_of_measured"], "status": status}
        if promote.decide(c, "region", r["code"], status, reasons, run_id):
            stats["changed"] += 1

    # De kantelvraag, alleen tussen regio's die volledig gemeten zijn.
    full = {k: v for k, v in scored.items() if not v["missing"]}
    if full:
        best = max(full.values(), key=lambda v: v["points"])["points"]
        stats["tipping"] = {k: tipping_point(comps[k], best)
                            for k, v in scored.items() if len(v["missing"]) == 1}
    return stats
