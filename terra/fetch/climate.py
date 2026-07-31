"""CHELSA naar neerslag per gemeente.

Dit is de stap die de vergelijkbaarheidseis van 50 procent naar boven duwt. De
regiovergelijking gebruikt nu stationsnormalen met verschillende referentieperioden
door elkaar (1981-2010 naast 1991-2020 naast een reeks 2014-2026). Een raster heeft
per definitie een uniforme periode, dus het probleem verdwijnt met de bron.

**Niet alleen het gemiddelde.** Een gemeente kan van 200 tot 1.200 meter lopen, en
een gemiddelde over zo'n polygoon herhaalt op gemeentelijk niveau precies de fout
die we op regionaal niveau net gerepareerd hebben. Daarom bewaart deze module per
gemeente ook min, max en de percentielen 10, 50 en 90. Het perceel bemonstert later
rechtstreeks uit het raster; de gemeentewaarde is een zeef, geen meting.

**De schaalfactor wordt niet gegokt.** CHELSA slaat waarden op als gehele getallen
met een schaalfactor die per variabele verschilt. We lezen wat het bestand zelf
zegt, en toetsen de uitkomst daarna aan een plausibel bereik. Klopt dat niet, dan
zegt de module dat hardop in plaats van tien keer te hoge neerslag weg te schrijven.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import db

# Jaarneerslag in mm op het Iberisch schiereiland en omgeving. Ruim genomen: dit is
# een controle op een orde van grootte, geen filter.
PLAUSIBEL_MM = (100.0, 4000.0)


def read_scaling(src) -> tuple[float, float]:
    """Schaal en verschuiving zoals het bestand ze zelf opgeeft."""
    scale = (src.scales or [1.0])[0] or 1.0
    offset = (src.offsets or [0.0])[0] or 0.0
    return float(scale), float(offset)


def sanity(values: list[float], bereik: tuple[float, float] = PLAUSIBEL_MM) -> dict:
    """Ligt de uitkomst in een plausibel bereik? Zo niet, welke kant op.

    Het meest waarschijnlijke foutscenario is een gemiste schaalfactor, en dat
    levert een factor tien. Dat is precies het soort fout dat er in een tabel nog
    steeds als een getal uitziet.
    """
    if not values:
        return {"ok": False, "reden": "geen waarden"}
    vals = sorted(values)
    med = vals[len(vals) // 2]
    lo, hi = bereik
    if lo <= med <= hi:
        return {"ok": True, "mediaan": round(med, 1)}
    factor = 10 if med > hi else 0.1
    return {"ok": False, "mediaan": round(med, 1),
            "reden": (f"mediaan {med:.0f} valt buiten {lo:.0f}-{hi:.0f} mm; "
                      f"vermoedelijk een gemiste schaalfactor van {factor}")}


def stats(values) -> dict:
    """Samenvatting per gemeente. Het bereik telt hier zwaarder dan het gemiddelde."""
    import numpy as np

    a = np.asarray(values, dtype="float64")
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"n": 0}
    p10, p50, p90 = (float(x) for x in np.percentile(a, [10, 50, 90]))
    return {"n": int(a.size), "mean": float(a.mean()), "min": float(a.min()),
            "max": float(a.max()), "p10": p10, "p50": p50, "p90": p90,
            "spread": round(float(a.max()) / float(a.min()), 2) if a.min() > 0 else None}


def sample(raster: Path, features: list[dict]) -> list[dict]:
    """Bemonstert per polygoon. Verwacht geometrieen in hetzelfde CRS als het raster.

    all_touched staat aan: een gemeente van een paar vierkante kilometer raakt op een
    raster van 1 km maar een handvol cellen, en zonder die vlag valt hij soms
    helemaal buiten de boot. Liever een cel te veel dan een gemeente zonder waarde.
    """
    import rasterio
    from rasterio.mask import mask as rio_mask

    out = []
    with rasterio.open(raster) as src:
        scale, offset = read_scaling(src)
        nodata = src.nodata
        for f in features:
            rec = {"code": f["code"]}
            try:
                arr, _ = rio_mask(src, [f["geometry"]], crop=True, all_touched=True,
                                  filled=False)
                band = arr[0]
                vals = band.compressed() if hasattr(band, "compressed") else band.ravel()
                if nodata is not None:
                    vals = vals[vals != nodata]
                rec.update(stats(vals * scale + offset))
            except Exception as e:
                rec.update({"n": 0, "error": f"{type(e).__name__}: {e}"})
            out.append(rec)
    return out


def municipalities_as_features(c, srid: int = 4326) -> list[dict]:
    """Gemeentegeometrieen uit de database, omgezet naar het CRS van het raster.

    CHELSA staat in EPSG:4326, de database in 3035. De omzetting doet PostGIS,
    want die weet het beter dan wij.
    """
    rows = db.q(c, """
        select code, st_asgeojson(st_transform(geom, %s)) as g
        from municipality where geom is not null order by code""", (srid,))
    return [{"code": r["code"], "geometry": json.loads(r["g"])} for r in rows]


OBS_SQL = """
insert into observation (subject_type,subject_id,variable,value_num,unit,quality,
                         comparable,source_id,observed_at,note,derived)
values ('municipality',%s,%s,%s,'mm/jaar','ver',true,'chelsa-climate',
        current_date,%s,%s)
on conflict (subject_type,subject_id,variable,observed_at) do update set
  value_num=excluded.value_num, quality=excluded.quality, note=excluded.note,
  derived=excluded.derived
"""


def write(c, samples: list[dict]) -> int:
    """Vijf waarden per gemeente, niet een.

    rain_mm is het gemiddelde en blijft de waarde waarop gefilterd wordt. De andere
    vier staan erbij zodat je kunt zien of dat gemiddelde iets betekent: een gemeente
    met p10 400 en p90 1.100 is geen gemeente met 750 mm.
    """
    rows = []
    for s in samples:
        if not s.get("n"):
            continue
        note = (f"n={s['n']} cellen, spreiding {s.get('spread')}x binnen de gemeente")
        # Alleen het gemiddelde is een meting; de vier andere zijn uitdrukkingen
        # van diezelfde meting. Ze gaan mee als derived=true zodat ze wel
        # beschikbaar zijn maar de rijpheidspoort niet opblazen.
        rows.append((s["code"], "rain_mm", s["mean"], note, False))
        for key, var in (("min", "rain_mm_min"), ("max", "rain_mm_max"),
                         ("p10", "rain_mm_p10"), ("p90", "rain_mm_p90")):
            rows.append((s["code"], var, s[key], None, True))
    return db.many(c, OBS_SQL, rows)


def load(c, raster: Path) -> dict:
    feats = municipalities_as_features(c)
    if not feats:
        return {"municipalities": 0,
                "note": "geen gemeentegeometrie; draai eerst terra.fetch.load_lau"}
    samples = sample(raster, feats)
    gemeten = [s for s in samples if s.get("n")]
    check = sanity([s["mean"] for s in gemeten])
    res = {"municipalities": len(feats), "sampled": len(gemeten),
           "zonder_waarde": len(feats) - len(gemeten), "sanity": check}
    if not check["ok"]:
        # Bewust niet wegschrijven. Tien keer te hoge neerslag ziet er in een tabel
        # nog steeds uit als een getal, en dat is het gevaarlijkste soort fout.
        res["written"] = 0
        res["gestopt"] = "sanity-controle niet gehaald, niets weggeschreven"
        return res
    res["written"] = write(c, gemeten)
    return res
