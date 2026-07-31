"""Haal een LAU-bestand op en laad het in de gemeentetabel.

    python -m terra.fetch.load_lau <url>

Bewust een dun laagje: sonderen, ophalen met hash, parsen, wegschrijven, en dan
in gewone taal zeggen wat er gebeurd is. Alle logica die iets kan betekenen zit
in terra/fetch/lau.py en is daar zonder netwerk getest.
"""
from __future__ import annotations

import json
import sys

from .. import db
from . import lau
from .base import download, probe


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("gebruik: python -m terra.fetch.load_lau <url>", file=sys.stderr)
        return 2
    url = argv[0]

    p = probe(url)
    print(p.line())
    if not p.ok:
        return 1
    if p.content_type and "html" in p.content_type:
        # Een landingspagina in plaats van een bestand. Beter nu stoppen dan een
        # parser laten struikelen over een <!DOCTYPE html>.
        print("dit adres geeft HTML terug, geen databestand", file=sys.stderr)
        return 1

    path, digest = download(url, name="lau.geojson")
    print(f"opgehaald: {path} ({path.stat().st_size/1e6:.1f} MB)\nsha256: {digest}")

    with db.conn() as c:
        with db.Run(c, "fetch_lau", "municipality") as run:
            res = lau.load(c, path)
            res["sha256"] = digest
            res["url"] = url
            run.stats = res
            c.commit()
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if not res["inserted"]:
        print("\nNUL GEMEENTEN INGELADEN. Hierboven staat onder 'diagnose' welke "
              "velden het bestand wel heeft; daar hoort de mapping op aangepast.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
