"""GISCO LAU naar de gemeentetabel.

Deze module is bewust in twee helften geknipt: het lezen en vertalen van de
kenmerken (pure functies, hier volledig getest tegen een fixture) en het schrijven
naar de database. De download zit er niet in. Zo kan de parser kloppen voordat er
ergens een bestand van tientallen megabytes over de lijn komt.

Tolerantie is opzet. Wij weten niet zeker hoe GISCO zijn velden noemt in de
jaargang die straks binnenkomt, dus de parser probeert een paar bekende namen en
zegt daarna wélke hij gebruikt heeft. Dat is beter dan een KeyError, en eerlijker
dan stil de eerste de beste kolom pakken.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import db

# Onze regiosleutel per NUTS2. Alleen regio's die met een NUTS2 samenvallen; de
# rest (Roemenie, Italie binnenland, Bulgarije) is een dossier en geen NUTS-eenheid.
REGION_BY_NUTS2 = {"ES43": "ext", "ES41": "cyl", "ES11": "gal",
                   "PT16": "bei", "PT18": "ale"}

ID_KEYS = ("GISCO_ID", "LAU_ID", "COMM_ID", "id")
NAME_KEYS = ("LAU_NAME", "NAME_LATN", "LAU_NAME_LATIN", "NSI_CODE", "name")
NUTS_KEYS = ("NUTS3_CODE", "NUTS_3", "NUTS3", "NUTS_CODE")
CNTR_KEYS = ("CNTR_CODE", "CNTR_ID", "COUNTRY")


def _pick(props: dict, keys: tuple[str, ...]) -> tuple[str | None, str | None]:
    for k in keys:
        if k in props and props[k] not in (None, ""):
            return str(props[k]), k
    return None, None


def detect_srid(features: list[dict]) -> int:
    """GeoJSON hoort in lengte- en breedtegraden te staan, maar GISCO publiceert
    ook bestanden in EPSG:3035 met dezelfde extensie. Aan de getallen is te zien
    welke van de twee het is, en dat is betrouwbaarder dan de bestandsnaam."""
    for f in features:
        for x, y in _coords(f.get("geometry") or {}):
            return 4326 if (abs(x) <= 180 and abs(y) <= 90) else 3035
    raise ValueError("geen coordinaten gevonden")


def _coords(geom: dict):
    c = geom.get("coordinates")
    stack = [c]
    while stack:
        cur = stack.pop()
        if isinstance(cur, (list, tuple)) and cur and isinstance(cur[0], (int, float)):
            yield cur[0], cur[1]
            return
        if isinstance(cur, (list, tuple)):
            stack.extend(cur)


def read(path: Path) -> list[dict]:
    data = json.loads(Path(path).read_text())
    return data["features"] if isinstance(data, dict) else list(data)


def to_rows(features: list[dict], region_by_nuts2: dict[str, str] | None = None) -> dict:
    """Vertaalt kenmerken naar rijen. Wat niet in een van onze regio's valt, wordt
    niet stil weggelaten maar geteld, per reden."""
    region_by_nuts2 = region_by_nuts2 or REGION_BY_NUTS2
    rows, skipped, used = [], {}, {}
    for f in features:
        p = f.get("properties") or {}
        code, k = _pick(p, ID_KEYS);   used.setdefault("id", k)
        name, k = _pick(p, NAME_KEYS); used.setdefault("name", k)
        nuts, k = _pick(p, NUTS_KEYS); used.setdefault("nuts", k)
        cntr, k = _pick(p, CNTR_KEYS); used.setdefault("country", k)
        if not code or not f.get("geometry"):
            skipped["zonder code of geometrie"] = skipped.get("zonder code of geometrie", 0) + 1
            continue
        region = region_by_nuts2.get((nuts or "")[:4])
        if not region:
            key = f"buiten onze regio's ({cntr or 'onbekend land'})"
            skipped[key] = skipped.get(key, 0) + 1
            continue
        rows.append({"code": code, "name": name or code, "region_code": region,
                     "geometry": f["geometry"]})
    return {"rows": rows, "skipped": skipped, "fields_used": used}


UPSERT = """
insert into municipality (code, region_code, name, geom, area_ha)
values (%s, %s, %s,
        st_multi(st_transform(st_setsrid(st_geomfromgeojson(%s), %s), 3035)),
        st_area(st_transform(st_setsrid(st_geomfromgeojson(%s), %s), 3035)) / 10000)
on conflict (code) do update set name=excluded.name, region_code=excluded.region_code,
  geom=excluded.geom, area_ha=excluded.area_ha
"""


def insert(c, rows: list[dict], srid: int) -> int:
    return db.many(c, UPSERT, [
        (r["code"], r["region_code"], r["name"],
         json.dumps(r["geometry"]), srid, json.dumps(r["geometry"]), srid)
        for r in rows])


def load(c, path: Path) -> dict:
    features = read(path)
    srid = detect_srid(features)
    parsed = to_rows(features)
    n = insert(c, parsed["rows"], srid)
    return {"features": len(features), "srid": srid, "inserted": n,
            "skipped": parsed["skipped"], "fields_used": parsed["fields_used"]}
