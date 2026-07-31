"""Bevorderen en afwijzen, met de reden vastgelegd.

Drie statussen, en de derde is de belangrijkste:
  promoted  -> door naar het volgende niveau
  rejected  -> afgewezen op een eigenschap, met de reden erbij
  pending   -> niet beoordeeld, want de meting ontbreekt

Zonder 'pending' schuift een ontbrekende meting stil op naar 'goedgekeurd'.
"""
from __future__ import annotations

import json

from . import db

Status = str


def decide(c, tier: str, subject_id: str, status: Status, reasons: list[str],
           run_id: int | None = None) -> bool:
    """Schrijft alleen als de uitkomst verandert. True bij een wijziging."""
    prev = db.q(c, """select status, reasons from promotion
                      where tier=%s and subject_id=%s
                      order by decided_at desc limit 1""", (tier, subject_id))
    if prev and prev[0]["status"] == status and (prev[0]["reasons"] or []) == reasons:
        return False
    db.x(c, """insert into promotion (tier,subject_id,status,reasons,run_id)
               values (%s,%s,%s,%s,%s)""",
         (tier, subject_id, status, json.dumps(reasons), run_id))
    return True


def verdict(ok: bool | None, reasons: list[str]) -> Status:
    """Vertaalt een drieledige uitkomst naar een status. None is niet False."""
    if ok is None:
        return "pending"
    return "promoted" if ok else "rejected"


def latest(c, tier: str) -> list[dict]:
    return db.q(c, """
        select p.subject_id, p.status, p.reasons, p.decided_at
        from promotion p
        join (select tier, subject_id, max(decided_at) as m
              from promotion where tier=%s group by tier, subject_id) l
          on l.subject_id=p.subject_id and l.m=p.decided_at
        where p.tier=%s
        order by p.status, p.subject_id""", (tier, tier))
