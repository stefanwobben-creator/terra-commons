"""Laag 0: land. Binair, en het gaat vooraf aan alle scoring.

Waarom eerst: een perfect perceel in een land waar de groep niet mag verwerven is
geen kandidaat maar tijdverlies. Deze laag is goedkoop en snijdt het meest weg.
"""
from __future__ import annotations

from .. import db, promote
from ..countries import BY_CODE
from ..rules import country_gate


def run(c, run_id: int | None = None) -> dict:
    rows = db.q(c, "select * from country order by code")
    stats = {"seen": len(rows), "promoted": 0, "rejected": 0, "pending": 0, "changed": 0}
    for r in rows:
        d = dict(r)
        d["parcel_geometry_open"] = BY_CODE[r["code"]]["parcel_geometry_open"]
        unknown = [k for k in ("buy_allowed", "use_obligation") if d.get(k) is None]
        if unknown:
            ok, reasons = None, [f"niet vastgesteld: {', '.join(unknown)}"]
        else:
            ok, reasons = country_gate(d)
        status = promote.verdict(ok, reasons)
        stats[status] += 1
        if promote.decide(c, "country", r["code"], status, reasons, run_id):
            stats["changed"] += 1
        db.x(c, "update country set gate_open=%s, gate_reason=%s where code=%s",
             (ok, "; ".join(reasons) or None, r["code"]))
    return stats
