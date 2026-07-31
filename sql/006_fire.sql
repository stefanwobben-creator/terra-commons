-- Brandperimeters, en de basiskans die eruit volgt.
--
-- De correctie die deze hele exercitie startte: een jaartotaal zegt niets. In 2022
-- brandde er in Zamora meer dan in de tien jaar ervoor samen. Wie op dat jaar
-- rekent, meet een staart. Wat je wilt weten is de kans dat een willekeurige
-- hectare in een willekeurig jaar brandt, en dat is een meerjarig gemiddelde.
--
-- Op gemeenteniveau komt daar een tweede probleem bij: een enkele grote brand
-- domineert een kleine gemeente volledig. Daarom telt deze laag ook het aantal
-- JAREN waarin er iets brandde, en niet alleen het aantal hectare. Een basiskans
-- die op een enkel jaar rust is geen basiskans, en dat hoort in de kwaliteitscode
-- terecht te komen in plaats van in een voetnoot.

create table if not exists fire_perimeter (
  id          bigserial primary key,
  source_id   text references source(id),
  ext_id      text,                      -- id zoals de bron hem noemt
  year        int not null,
  name        text,
  area_ha     numeric,
  geom        geometry(MultiPolygon, 3035) not null,
  loaded_at   timestamptz not null default now(),
  unique (source_id, ext_id, year)
);
create index if not exists fire_geom_ix on fire_perimeter using gist (geom);
create index if not exists fire_year_ix on fire_perimeter (year);

-- Verbrand oppervlak per gemeente per jaar. De doorsnede telt, niet de perimeter:
-- een brand van 30.000 ha die voor een tiende in deze gemeente ligt, telt hier voor
-- 3.000 ha en niet voor 30.000.
create or replace view v_fire_by_municipality_year as
select m.code as muni_code, f.year,
       sum(st_area(st_intersection(m.geom, f.geom))) / 10000.0 as burned_ha
from municipality m
join fire_perimeter f on st_intersects(m.geom, f.geom)
group by m.code, f.year;

-- De basiskans zelf, met alles erbij wat nodig is om hem te wantrouwen.
drop view if exists v_fire_base_rate;
create view v_fire_base_rate as
with jaren as (
  -- Het venster is de PERIODE, niet het aantal jaren waarin er toevallig iets
  -- brandde. Dat verschil is een denominatorfout van hetzelfde type als het
  -- jaartotaal dat deze hele laag moest vervangen: tel je alleen brandjaren, dan
  -- deel je door een kleiner getal en komt elke basiskans te hoog uit.
  select min(year) as van, max(year) as tot,
         (max(year) - min(year) + 1)::bigint as n_jaar
  from fire_perimeter
), per_gemeente as (
  select m.code, m.area_ha,
         coalesce(sum(v.burned_ha), 0)            as burned_ha_totaal,
         count(distinct v.year)                   as brandjaren,
         max(v.burned_ha)                         as grootste_jaar
  from municipality m
  left join v_fire_by_municipality_year v on v.muni_code = m.code
  group by m.code, m.area_ha
)
select p.code, p.area_ha, round(p.burned_ha_totaal::numeric, 1) as burned_ha_totaal,
       p.brandjaren, j.n_jaar as venster_jaren, j.van, j.tot,
       round((100.0 * p.burned_ha_totaal / nullif(p.area_ha, 0) / nullif(j.n_jaar, 0))::numeric, 4)
                                                              as rate_pct_per_jaar,
       case when p.burned_ha_totaal > 0
            then round((p.area_ha * j.n_jaar / nullif(p.burned_ha_totaal, 0))::numeric)
       end                                                    as terugkeer_jaren,
       -- Rust de kans op een enkel jaar? Dan is het een waarneming en geen kans.
       (p.brandjaren <= 1 and p.burned_ha_totaal > 0)          as rust_op_een_jaar,
       round((100.0 * coalesce(p.grootste_jaar, 0) / nullif(p.burned_ha_totaal, 0))::numeric)
                                                              as aandeel_grootste_jaar
from per_gemeente p cross join jaren j;
