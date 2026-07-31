"""Regiowaarden afleiden uit de gemeentelaag.

Dit is de goedkoopste stap in het hele project: geen download, een query.

De regiovergelijking hangt op vergelijkbaarheid. Neerslag stond daar op
niet-vergelijkbaar, want de acht regio's kwamen uit stationsnormalen met
verschillende referentieperioden (1981-2010 naast 1991-2020 naast een reeks uit
2014-2026). Sinds de gemeentelaag er is komt neerslag uit een raster met een
uniforme periode. Door het regiogemiddelde daaruit te herberekenen wordt dezelfde
variabele in een keer wel vergelijkbaar, zonder dat er een byte bijkomt.

Oppervlaktegewogen, want een regio is geen verzameling gemeenten van gelijke
grootte: Cáceres heeft gemeenten van 20 en van 800 km2 naast elkaar. Het
ongewogen gemiddelde zou de kleine bergdorpjes even zwaar laten wegen als een
halve provincie.
"""
from __future__ import annotations

from . import db

SQL_REGIO_NEERSLAG = """
with per_regio as (
  select m.region_code,
         sum(o.value_num * m.area_ha) / nullif(sum(m.area_ha), 0) as mm_gewogen,
         min(o.value_num) as mm_min,
         max(o.value_num) as mm_max,
         count(*)         as n_gemeenten,
         sum(m.area_ha)   as ha
  from municipality m
  join v_observation_current o
    on o.subject_type = 'municipality' and o.subject_id = m.code
   and o.variable = 'rain_mm' and o.quality <> 'mis'
  where m.area_ha > 0
  group by m.region_code
)
insert into observation (subject_type, subject_id, variable, value_num, unit,
                         quality, comparable, source_id, observed_at, note)
select 'region', region_code, 'rain_mm', round(mm_gewogen::numeric, 1), 'mm/jaar',
       'ver', true, 'chelsa-climate', current_date,
       'oppervlaktegewogen uit ' || n_gemeenten || ' gemeenten, raster 1 km, '
       || 'periode 1981-2010; spreiding ' || round(mm_min::numeric) || ' tot '
       || round(mm_max::numeric) || ' mm binnen de regio'
from per_regio
on conflict (subject_type, subject_id, variable, observed_at) do update set
  value_num = excluded.value_num, quality = excluded.quality,
  comparable = excluded.comparable, source_id = excluded.source_id,
  note = excluded.note
returning subject_id, value_num, note
"""


def region_rain(c) -> list[dict]:
    """Herberekent regioneerslag uit de gemeentelijke rasterwaarden.

    De oude stationsnormaal blijft in de tabel staan met zijn eigen datum. Hij
    telt alleen niet meer mee, want v_readiness kijkt sinds sql/004 naar de meest
    recente meting per cel. Weggooien zou de geschiedenis wissen, en juist het
    verschil tussen die twee getallen is het interessante.
    """
    return db.q(c, SQL_REGIO_NEERSLAG)


def rain_thresholds(c) -> list[dict]:
    """Hoeveel gemeenten halen welke ondergrens. Zie v_rain_thresholds."""
    return db.q(c, "select * from v_rain_thresholds")


def municipality_rain(c, limit: int | None = None) -> list[dict]:
    """Per gemeente de vijf neerslagwaarden, plus de spreiding binnen de gemeente.

    Dit hoort in het export-bestand, en dat is niet cosmetisch: de database van de
    workflow is een wegwerpmachine. Zodra de taak klaar is bestaat hij niet meer.
    Wat niet in de repo terechtkomt, is weg.
    """
    rows = db.q(c, """
        select m.code, m.name, m.region_code, round(m.area_ha) as area_ha,
               max(o.value_num) filter (where o.variable='rain_mm')     as mm,
               max(o.value_num) filter (where o.variable='rain_mm_min') as mm_min,
               max(o.value_num) filter (where o.variable='rain_mm_max') as mm_max,
               max(o.value_num) filter (where o.variable='rain_mm_p10') as mm_p10,
               max(o.value_num) filter (where o.variable='rain_mm_p90') as mm_p90
        from municipality m
        join v_observation_current o
          on o.subject_type='municipality' and o.subject_id=m.code
        where o.variable like 'rain\\_mm%%'
        group by m.code, m.name, m.region_code, m.area_ha
        order by m.code
    """ + (f" limit {int(limit)}" if limit else ""))
    for r in rows:
        for k in ("mm", "mm_min", "mm_max", "mm_p10", "mm_p90", "area_ha"):
            if r.get(k) is not None:
                r[k] = round(float(r[k]), 1)
        if r.get("mm_min"):
            r["spread"] = round(r["mm_max"] / r["mm_min"], 2)
    return rows
