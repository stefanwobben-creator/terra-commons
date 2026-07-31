"""Brandperimeters naar een basiskans per gemeente.

Dit is de cel die de rangorde beslist. Extremadura stond eerste met een leeg
brandvak, en het omslagpunt lag op vijftien van de vijfentwintig punten: daarboven
blijft Extremadura eerste, daaronder wint Castilla y León. Eén ontbrekende meting
droeg de hele conclusie.

**Meerjarig, niet een jaartotaal.** In 2022 brandde er in Zamora meer dan in de
tien jaar ervoor samen. Wie op dat jaar rekent meet een staart en geen kans.

**En op gemeenteniveau komt daar iets bij.** Eén grote brand domineert een kleine
gemeente volledig. Een gemeente met 3.000 verbrande hectare in 2022 en niets in de
negen jaar daarvoor heeft geen basiskans van 2 procent per jaar; die heeft één
brand gehad. Daarom telt deze module ook het aantal jaren waarin er iets brandde,
en zakt de kwaliteitscode naar 'ind' zodra de kans op een enkel jaar rust. Dat is
dezelfde fout als hierboven, één niveau lager, en hij verdient dezelfde behandeling.

De parser is net zo tolerant als die van de gemeentegrenzen: welke veldnamen EFFIS
gebruikt weten we niet zeker, dus we proberen er een paar en rapporteren welke
gepakt is. Bij nul treffers volgt een diagnose in plaats van een nul.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import db
from . import lau

YEAR_KEYS = ("YEAR", "year", "FIREDATE", "firedate", "INITIALDATE", "initialdate",
             "DATE", "date", "ANO", "anio")
ID_KEYS = ("id", "ID", "OBJECTID", "objectid", "fid", "gid")
NAME_KEYS = ("PLACE_NAME", "place_name", "NAME", "name", "COMMUNE", "municipality")
AREA_KEYS = ("AREA_HA", "area_ha", "AREA", "area", "BURNTAREA", "burnt_area")


def parse_year(value) -> int | None:
    """Een jaartal uit wat de bron ook maar aanlevert.

    EFFIS geeft soms een jaar, soms een volledige datum, soms een tijdstempel.
    Alles wat op vier cijfers tussen 1980 en 2100 lijkt telt als jaar; de rest niet.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)) and 1980 <= int(value) <= 2100:
        return int(value)
    m = re.search(r"(19[89]\d|20\d\d|21\d\d)", str(value))
    if not m:
        return None
    jaar = int(m.group(1))
    return jaar if 1980 <= jaar <= 2100 else None


def to_rows(features: list[dict]) -> dict:
    rows, skipped, used = [], {}, {}
    for f in features:
        p = f.get("properties") or {}
        ext_id, k = lau._pick(p, ID_KEYS);   used.setdefault("id", k)
        naam, k = lau._pick(p, NAME_KEYS);   used.setdefault("naam", k)
        opp, k = lau._pick(p, AREA_KEYS);    used.setdefault("oppervlak", k)
        jaar = None
        for key in YEAR_KEYS:
            if key in p:
                jaar = parse_year(p[key])
                if jaar:
                    used.setdefault("jaar", key)
                    break
        if not f.get("geometry"):
            skipped["zonder geometrie"] = skipped.get("zonder geometrie", 0) + 1
            continue
        if not jaar:
            skipped["zonder bruikbaar jaartal"] = skipped.get("zonder bruikbaar jaartal", 0) + 1
            continue
        try:
            opp_num = float(str(opp).replace(",", ".")) if opp else None
        except ValueError:
            opp_num = None
        rows.append({"ext_id": ext_id, "year": jaar, "name": naam, "area_ha": opp_num,
                     "geometry": f["geometry"]})
    out = {"rows": rows, "skipped": skipped, "fields_used": used}
    if not rows:
        out["diagnose"] = lau.diagnose(features)
    return out


INSERT = """
insert into fire_perimeter (source_id, ext_id, year, name, area_ha, geom)
values ('effis-fires', %s, %s, %s, %s,
        st_multi(st_transform(st_setsrid(st_geomfromgeojson(%s), %s), 3035)))
on conflict (source_id, ext_id, year) do update set
  name=excluded.name, area_ha=excluded.area_ha, geom=excluded.geom
"""


def insert(c, rows: list[dict], srid: int) -> int:
    return db.many(c, INSERT, [(r["ext_id"], r["year"], r["name"], r["area_ha"],
                                json.dumps(r["geometry"]), srid) for r in rows])


OBS = """
insert into observation (subject_type,subject_id,variable,value_num,unit,quality,
                         comparable,source_id,observed_at,note,derived)
values ('municipality',%s,%s,%s,%s,%s,true,'effis-fires',current_date,%s,%s)
on conflict (subject_type,subject_id,variable,observed_at) do update set
  value_num=excluded.value_num, quality=excluded.quality, note=excluded.note,
  derived=excluded.derived
"""


def write_rates(c) -> dict:
    """Basiskans per gemeente wegschrijven, met de kwaliteitscode die hij verdient.

    'ver' als de kans op meerdere brandjaren rust, 'ind' als hij op een enkel jaar
    rust of als er in het venster niets brandde. Dat tweede is geen nul maar een
    ondergrens: afwezigheid van waarneming in tien jaar zegt iets, maar niet dat de
    kans nul is.
    """
    rijen = db.q(c, "select * from v_fire_base_rate")
    if not rijen:
        return {"gemeenten": 0, "note": "geen gemeenten of geen perimeters ingeladen"}
    obs, tellers = [], {"ver": 0, "ind": 0}
    for r in rijen:
        venster, dekking = r["venster_jaren"] or 0, r["dekking_jaren"] or 0
        basis = f"venster {r['van']} tot {r['tot']} ({venster} jaar), dekking {dekking}"
        if r["venster_niet_vol"]:
            # De noemer blijft vijftien. Hem verkleinen zou de kans mooier maken en
            # het gat verbergen; dit is precies de fout die deze laag moest oplossen.
            kwaliteit = "ind"
            note = (f"{basis}; het venster is niet vol, dus dit is een ondergrens. "
                    f"De noemer blijft {venster} jaar, met opzet.")
        elif r["burned_ha_totaal"] and not r["rust_op_een_jaar"]:
            kwaliteit = "ver"
            note = (f"{basis}; {r['brandjaren']} brandjaren, grootste jaar is "
                    f"{r['aandeel_grootste_jaar']}% van het totaal")
        elif r["burned_ha_totaal"]:
            kwaliteit = "ind"
            note = f"{basis}; rust op een enkel brandjaar, dus een waarneming en geen kans"
        else:
            kwaliteit = "ind"
            note = f"{basis}; niets verbrand, dat is een ondergrens en geen nul"
        tellers[kwaliteit] += 1
        obs.append((r["code"], "fire_rate_pct", float(r["rate_pct_per_jaar"] or 0),
                    "%/jaar", kwaliteit, note, False))
        obs.append((r["code"], "fire_burned_ha", float(r["burned_ha_totaal"] or 0),
                    "ha", kwaliteit, None, True))
        if r["terugkeer_jaren"]:
            obs.append((r["code"], "fire_return_years", float(r["terugkeer_jaren"]),
                        "jaar", kwaliteit, None, True))
    n = db.many(c, OBS, obs)
    return {"gemeenten": len(rijen), "observaties": n, "kwaliteit": tellers}


def load(c, path: Path) -> dict:
    features = lau.read(path)
    srid = lau.detect_srid(features)
    parsed = to_rows(features)
    n = insert(c, parsed["rows"], srid)
    res = {"features": len(features), "srid": srid, "perimeters": n,
           "skipped": parsed["skipped"], "fields_used": parsed["fields_used"]}
    if "diagnose" in parsed:
        res["diagnose"] = parsed["diagnose"]
        return res
    res["rates"] = write_rates(c)
    return res
