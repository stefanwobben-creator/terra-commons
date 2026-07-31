-- Een vast venster van vijftien jaar, en de dekking ervan apart gemeten.
--
-- Waarom vast en niet afgeleid: eerder was het venster "de jaren die in het bestand
-- staan". Dat is geen keuze maar een bijproduct van de download. Levert de bron drie
-- jaar, dan deel je door drie en komt elke basiskans vijf keer te hoog uit, zonder
-- dat iemand dat ziet.
--
-- Vijftien jaar is een keuze met een reden: daarvoor verschilden landgebruik en
-- brandbestrijding in Spanje te veel om er een kans uit te destilleren.
--
-- Twee getallen dus, en ze zijn niet hetzelfde:
--   venster_jaren  = 15, altijd. De noemer.
--   dekking_jaren  = hoeveel van die vijftien er daadwerkelijk data hebben.
-- Loopt de dekking achter op het venster, dan is de kans een onderschatting en
-- zakt de kwaliteitscode. De noemer verandert niet, want dat zou de fout verbergen.

drop view if exists v_fire_base_rate;
drop view if exists v_fire_by_municipality_year;

create or replace view v_fire_window as
with grens as (select max(year) as tot from fire_perimeter)
select g.tot - 14 as van, g.tot, 15 as venster_jaren,
       (select count(distinct f.year) from fire_perimeter f
        where f.year between g.tot - 14 and g.tot) as dekking_jaren
from grens g where g.tot is not null;

create view v_fire_by_municipality_year as
select m.code as muni_code, f.year,
       sum(st_area(st_intersection(m.geom, f.geom))) / 10000.0 as burned_ha
from municipality m
join fire_perimeter f on st_intersects(m.geom, f.geom)
join v_fire_window w on f.year between w.van and w.tot
group by m.code, f.year;

create view v_fire_base_rate as
with per_gemeente as (
  select m.code, m.area_ha,
         coalesce(sum(v.burned_ha), 0) as burned_ha_totaal,
         count(distinct v.year)        as brandjaren,
         max(v.burned_ha)              as grootste_jaar
  from municipality m
  left join v_fire_by_municipality_year v on v.muni_code = m.code
  group by m.code, m.area_ha
)
select p.code, p.area_ha, round(p.burned_ha_totaal::numeric, 1) as burned_ha_totaal,
       p.brandjaren, w.venster_jaren, w.dekking_jaren, w.van, w.tot,
       round((100.0 * p.burned_ha_totaal / nullif(p.area_ha,0) / w.venster_jaren)::numeric, 4)
                                                              as rate_pct_per_jaar,
       case when p.burned_ha_totaal > 0
            then round((p.area_ha * w.venster_jaren / nullif(p.burned_ha_totaal,0))::numeric)
       end                                                    as terugkeer_jaren,
       (p.brandjaren <= 1 and p.burned_ha_totaal > 0)          as rust_op_een_jaar,
       (w.dekking_jaren < w.venster_jaren)                     as venster_niet_vol,
       round((100.0 * coalesce(p.grootste_jaar,0) / nullif(p.burned_ha_totaal,0))::numeric)
                                                              as aandeel_grootste_jaar
from per_gemeente p cross join v_fire_window w;
