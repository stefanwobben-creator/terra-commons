"""Haal het CHELSA-raster op en zet neerslag per gemeente in de database.

    python -m terra.fetch.load_climate <url>

Het raster is 655 MB. Dat is prima op een runner (wegwerpschijf, snelle lijn) en
onhandig op een laptop, dus dit hoort in de workflow te draaien en niet lokaal.
De download komt in de cache met een sha256, dus twee keer draaien haalt niets
opnieuw op.
"""
from __future__ import annotations

import json
import sys

from .. import db
from . import climate
from .base import download, probe


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("gebruik: python -m terra.fetch.load_climate <url>", file=sys.stderr)
        return 2
    url = argv[0]

    p = probe(url)
    print(p.line())
    if not p.ok:
        return 1
    if p.content_type and "tiff" not in (p.content_type or ""):
        print(f"verwacht image/tiff, kreeg {p.content_type}", file=sys.stderr)
        return 1

    path, digest = download(url, name="rain.tif")
    print(f"opgehaald: {path} ({path.stat().st_size/1e6:.0f} MB)\nsha256: {digest}")

    with db.conn() as c:
        with db.Run(c, "fetch_climate", "municipality") as run:
            res = climate.load(c, path)
            res["sha256"] = digest
            res["url"] = url
            run.stats = res
            c.commit()
    print(json.dumps(res, indent=1, ensure_ascii=False))
    if not res.get("written"):
        print("niets weggeschreven; lees de sanity-uitkomst hierboven", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
