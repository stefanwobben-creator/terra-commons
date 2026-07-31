"""Haal brandperimeters op en bereken de basiskans per gemeente.

    python -m terra.fetch.load_fires <url>

Werkt met elke bron die een FeatureCollection met polygonen en een jaartal levert.
Welke dat wordt hangt af van wat de sonde zegt: het EFFIS-endpoint gaf tot nu toe
een pagina in plaats van een document, en als dat zo blijft is brand handmatig werk
en hoort het in v_manual_debt in plaats van in een cronjob.
"""
from __future__ import annotations

import json
import sys

from .. import db
from . import fires
from .base import download, probe


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("gebruik: python -m terra.fetch.load_fires <url>", file=sys.stderr)
        return 2
    url = argv[0]

    p = probe(url)
    print(p.line())
    if not p.ok:
        return 1
    if p.content_type and "html" in p.content_type:
        print("dit adres geeft HTML terug, geen databestand. Draai de sonde met "
              "--peek om te zien wat er staat.", file=sys.stderr)
        return 1

    path, digest = download(url, name="fires.geojson")
    print(f"opgehaald: {path} ({path.stat().st_size/1e6:.1f} MB)\nsha256: {digest}")

    with db.conn() as c:
        with db.Run(c, "fetch_fires", "municipality") as run:
            res = fires.load(c, path)
            res["sha256"], res["url"] = digest, url
            run.stats = res
            c.commit()
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    if not res.get("perimeters"):
        print("\nNUL PERIMETERS. Hierboven staat onder 'diagnose' welke velden het "
              "bestand wel heeft.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
