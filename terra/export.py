"""Van database naar site.

De site is statisch, dus zij kan geen SQL draaien. Dit script schrijft de gemeten
getallen naar `site/data.json`; de pagina leest dat bestand en overschrijft haar
eigen ingebouwde waarden ermee.

Waarom dit belangrijker is dan het klinkt: de cijfers stonden als JavaScript-
constanten in de pagina. Dat is dezelfde herkomstfout als een advertentie zonder
URL, een niveau hoger: de pagina was een bron zonder bron. Vanaf nu is er precies
een plek waar een getal ontstaat, en de pagina is er niet.

`tests/test_export.py` faalt als data.json en de database uiteenlopen. Dat is de
enige fout in dit project die je nooit ziet, omdat beide kanten er kloppend uitzien.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .config import THRESHOLDS
from .load_seed import VAR_MAP
from .registry import BY_ID, SOURCES, summary
from .scoring import weight_audit
from . import aggregate
from .tiers import t1_region, t3_parcel

OUT = Path(__file__).resolve().parent.parent / "site" / "data.json"
SITE_KEY = {v: k for k, v in VAR_MAP.items()}   # db-variabele -> sleutel op de site


def build(c, generated_at: str | None = None) -> dict:
    readiness = {r["tier"]: {k: (int(v) if k.endswith("_pct") and v is not None else v)
                             for k, v in r.items() if k != "tier"}
                 for r in db.q(c, "select * from v_readiness")}

    regions: dict[str, dict] = {}
    for r in db.q(c, "select code, name, country_code, nuts2 from region order by code"):
        regions[r["code"]] = {"name": r["name"], "country": r["country_code"],
                              "nuts2": r["nuts2"], "q": {}, "values": {}}
    for o in db.q(c, """select subject_id, variable, value_num, value_txt, quality
                        from observation where subject_type='region'"""):
        key = SITE_KEY.get(o["variable"])
        if not key or o["subject_id"] not in regions:
            continue
        regions[o["subject_id"]]["q"][key] = o["quality"]
        regions[o["subject_id"]]["values"][key] = {"num": o["value_num"],
                                                   "txt": o["value_txt"]}

    scores = t1_region._components()
    for code, sc in scores.items():
        if code in regions:
            regions[code]["score"] = sc
    for p in db.q(c, """select subject_id, status, reasons from promotion p
                        where tier='region' and decided_at =
                          (select max(decided_at) from promotion
                           where tier='region' and subject_id=p.subject_id)"""):
        if p["subject_id"] in regions:
            regions[p["subject_id"]]["status"] = p["status"]
            regions[p["subject_id"]]["reasons"] = p["reasons"]

    countries = {r["code"]: {"name": r["name"], "gate_open": r["gate_open"],
                             "gate_reason": r["gate_reason"],
                             "in_scope": r["in_scope"], "scope_note": r["scope_note"]}
                 for r in db.q(c, "select * from country order by code")}

    # Buiten de scope is niet hetzelfde als weg. De pagina hoort te kunnen laten
    # zien welk onderzoek er ligt en waarom het even niet meetelt.
    scope = {"in": [k for k, v in countries.items() if v["in_scope"]],
             "out": [dict(r) for r in db.q(c, "select * from v_out_of_scope")]}

    funnel: dict[str, dict] = {}
    for r in db.q(c, "select * from v_funnel"):
        funnel.setdefault(r["tier"], {})[r["status"]] = r["n"]

    quarantine = {
        "by_region": [dict(r) for r in db.q(c, "select * from v_quarantine_report")],
        "dehesa": t3_parcel.dry_run_quarantine(c, "dehesa"),
        "rewild": t3_parcel.dry_run_quarantine(c, "rewild"),
    }
    quarantine["n"] = quarantine["dehesa"]["n"]
    quarantine["complete"] = quarantine["n"] >= 30

    def _bron(rid, veld, terugval=None):
        s = BY_ID.get(rid)
        return getattr(s, veld, terugval) if s else terugval

    debt = [{"id": r["id"], "name": _bron(r["id"], "name", r["name"]),
             "tier": r["tier"], "cadence": r["cadence"], "overdue": r["overdue"],
             "unlocks": _bron(r["id"], "unlocks"),
             "unlocks_en": _bron(r["id"], "unlocks_en")}
            for r in db.q(c, "select * from v_manual_debt")]

    # Bronnen die wel automatisch kunnen maar nog geen ophaler hebben. Die horen
    # ook op de wachtlijst, anders lijkt "tien automatiseerbaar" op "tien geregeld".
    from .fetch.sources import ALL as SONDE
    gesondeerd = {x.id for x in SONDE}
    wacht_auto = [{"id": s_.id, "name": s_.name, "tier": s_.tier,
                   "unlocks": s_.unlocks, "unlocks_en": s_.unlocks_en,
                   "gesondeerd": s_.id in gesondeerd}
                  for s_ in SOURCES if s_.automatable and s_.unlocks]

    # De database van de workflow is een wegwerpmachine: zodra de taak klaar is
    # bestaat hij niet meer. Wat hier niet in komt, is weg. Daarom gaan de
    # gemeentewaarden mee en niet alleen de tellingen erover.
    gemeenten = aggregate.municipality_rain(c)

    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "thresholds": dict(zip(("rel", "cmp", "cov"), THRESHOLDS)),
        "readiness": readiness,
        "blocking_vars": [dict(r) for r in db.q(c, "select * from v_blocking_vars")],
        "countries": countries,
        "regions": regions,
        "funnel": funnel,
        "quarantine": quarantine,
        "sources": summary(),
        "manual_debt": debt,
        "waiting_automatable": wacht_auto,
        "weight_audit": weight_audit(),
        "scope": scope,
        "municipalities": gemeenten,
        "rain_thresholds": [dict(r) for r in aggregate.rain_thresholds(c)],
    }


def main(path: Path | None = None) -> dict:
    path = path or OUT
    with db.conn() as c:
        data = build(c)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=str))
    return data


if __name__ == "__main__":
    d = main()
    r = d["readiness"].get("region", {})
    print(f"site/data.json geschreven: {len(d['regions'])} regio's, poort "
          f"{r.get('reliable_pct')}/{r.get('comparable_pct')}/{r.get('complete_pct')}, "
          f"quarantaine {d['quarantine']['n']}")
