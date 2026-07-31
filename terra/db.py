"""Dunne laag boven psycopg. Twee dingen die verder nergens herhaald worden:
een verbinding, en een run-registratie zodat elke taak een spoor achterlaat dat
je later kunt aanwijzen."""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterable, Sequence

try:
    import psycopg
    from psycopg.rows import dict_row
except ModuleNotFoundError as e:  # pragma: no cover
    # Een kale ModuleNotFoundError laat iemand denken dat de repo stuk is, terwijl
    # het antwoord meestal is: je hoeft dit lokaal helemaal niet te draaien. De
    # keten draait in GitHub Actions, met een database die daar wordt opgezet.
    raise ModuleNotFoundError(
        "psycopg ontbreekt, dus deze module kan geen database benaderen.\n"
        "\n"
        "Grote kans dat je dit lokaal niet hoeft te draaien: alles wat een database\n"
        "nodig heeft (inname, nightly, export) draait in de workflow 'data' op\n"
        "GitHub, en die zet zijn eigen PostgreSQL met PostGIS op. Pushen is genoeg.\n"
        "\n"
        "Wil je het toch lokaal, dan heb je twee dingen nodig en niet een:\n"
        "  1. pip install -r requirements.txt\n"
        "  2. een draaiende PostgreSQL 16 met PostGIS 3.4, plus scripts/bootstrap.sh\n"
        "Zonder dat tweede loopt hij een stap verderop alsnog vast op de verbinding.\n"
    ) from e

from .config import DSN


@contextmanager
def conn(dsn: str | None = None):
    with psycopg.connect(dsn or DSN, row_factory=dict_row) as c:
        yield c


def q(c, sql: str, params: Sequence[Any] | None = None) -> list[dict]:
    with c.cursor() as cur:
        cur.execute(sql, params or ())
        if cur.description is None:
            return []
        return cur.fetchall()


def x(c, sql: str, params: Sequence[Any] | None = None) -> int:
    with c.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount


def many(c, sql: str, rows: Iterable[Sequence[Any]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    with c.cursor() as cur:
        cur.executemany(sql, rows)
    return len(rows)


class Run:
    """Contextmanager die start, einde en uitkomst van een taak vastlegt.

    De reden dat dit een tabel is en geen logbestand: de vraag 'wanneer is de
    brandbasis voor het laatst echt herberekend' moet met SQL te beantwoorden
    zijn, niet met grep door container-logs die Render weggooit.
    """

    def __init__(self, c, task: str, tier: str | None = None):
        self.c, self.task, self.tier = c, task, tier
        self.id: int | None = None
        self.stats: dict = {}

    def __enter__(self) -> "Run":
        row = q(self.c, "insert into run (task, tier) values (%s,%s) returning id",
                (self.task, self.tier))[0]
        self.id = row["id"]
        self.c.commit()
        return self

    def __exit__(self, et, ev, tb) -> bool:
        x(self.c, """update run set finished_at=now(), ok=%s, stats=%s, error=%s
                     where id=%s""",
          (et is None, json.dumps(self.stats),
           None if et is None else f"{et.__name__}: {ev}", self.id))
        self.c.commit()
        return False  # fouten niet opslokken; een stille nacht is erger dan een rode
