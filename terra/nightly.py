"""De nacht. Van land naar regio naar gemeente naar perceel, in die volgorde.

Twee ontwerpkeuzes die het verschil maken tussen een cron en een pijplijn:

1. Cadans in de database, niet in de crontab. Een bron met cadans 'annual' wordt
   niet 365 keer per jaar opgehaald omdat de cron elke nacht draait. Elke run kijkt
   wat er vandaag aan de beurt is (source.next_due). Idempotent, tweemaal draaien
   kost niets.

2. Handmatige schuld wordt geteld, niet weggelaten. Zeven van de zeventien bronnen
   zijn niet te automatiseren, waaronder de poort K5. Elke run eindigt met die lijst,
   zodat 'automatisch bijgewerkt' niet meer klinkt dan het is.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from . import db
from .config import THRESHOLDS
from .tiers import t0_country, t1_region, t2_municipality, t3_parcel

STEP = {"nightly": 1, "weekly": 7, "seasonal": 90, "annual": 365}


def due_sources(c, today: date | None = None) -> list[dict]:
    today = today or date.today()
    return db.q(c, """select * from source
                      where automatable and cadence <> 'on_demand'
                        and (next_due is null or next_due <= %s)
                      order by tier, id""", (today,))


def mark_done(c, source_id: str, cadence: str, today: date | None = None) -> None:
    today = today or date.today()
    nxt = None if cadence == "once" else today + timedelta(days=STEP.get(cadence, 365))
    db.x(c, "update source set last_run=now(), next_due=%s where id=%s", (nxt, source_id))


def readiness(c) -> list[dict]:
    return db.q(c, "select * from v_readiness order by tier")


def manual_debt(c) -> list[dict]:
    return db.q(c, "select * from v_manual_debt")


def main(intent: str = "dehesa", today: date | None = None) -> dict:
    out: dict = {"date": str(today or date.today()), "intent": intent}
    with db.conn() as c:
        due = due_sources(c, today)
        # Het ophalen zelf zit per bron in eigen modules; die zijn er nog niet voor
        # alle zeventien. Wat hier al klopt is de planning, en dat is het deel dat
        # anders in een crontab verstopt raakt.
        out["fetch_implemented"] = []
        out["fetch_todo"] = [s["id"] for s in due]

        with db.Run(c, "nightly", "all") as run:
            out["t0_country"] = t0_country.run(c, run.id); c.commit()
            out["t1_region"] = t1_region.run(c, run.id); c.commit()
            out["t2_municipality"] = t2_municipality.run(c, run.id, intent); c.commit()
            out["t3_parcel"] = t3_parcel.run(c, run.id, intent); c.commit()
            out["quarantine_dry_run"] = t3_parcel.dry_run_quarantine(c, intent)
            run.stats = {k: v for k, v in out.items() if k.startswith("t")}

        out["readiness"] = [dict(r) for r in readiness(c)]
        out["thresholds"] = dict(zip(("reliable", "comparable", "complete"), THRESHOLDS))
        out["manual_debt"] = [r["id"] for r in manual_debt(c) if r["overdue"]]
        c.commit()
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1, default=str))
