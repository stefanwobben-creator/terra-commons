-- Twee correcties op de rijpheidspoort, allebei gevonden toen de gemeentelaag
-- er voor het eerst echt in zat.

-- 1. Afgeleide waarden zijn geen aparte metingen.
--
-- Per gemeente schrijven we vijf getallen weg: gemiddelde, min, max, p10 en p90.
-- Dat zijn vijf uitdrukkingen van dezelfde meting. Ze meetellen als vijf cellen
-- laat de laag vijf keer beter gedekt lijken dan hij is. Ze blijven wel staan,
-- want het bereik is juist waar het om gaat; ze tellen alleen niet mee in de poort.
alter table observation add column if not exists derived boolean not null default false;

update observation set derived = true
where variable ~ '_(min|max|p10|p50|p90)$' and not derived;

-- 2. Alleen de meest recente meting per cel telt.
--
-- v_readiness telde elke rij in observation. Zodra dezelfde variabele op een
-- tweede datum opnieuw gemeten wordt, telt hij dus twee keer mee, en dan gaan de
-- percentages schuiven door het opnieuw meten in plaats van door de meting.
-- Dat wordt acuut nu we regioneerslag uit het raster gaan afleiden: die komt
-- naast de oude stationsnormaal te staan.
create or replace view v_observation_current as
select distinct on (subject_type, subject_id, variable) *
from observation
order by subject_type, subject_id, variable, observed_at desc, id desc;

-- 3. Vergelijkbaarheid is een eigenschap van de variabele, niet van een cel.
--
-- v_readiness telde een variabele als vergelijkbaar zodra EEN cel dat was. Bij
-- gemengde invoer (drie regio's uit het raster, vijf nog uit stationsnormalen)
-- kleurde die variabele daarmee ten onrechte groen. Precies de stille
-- overschatting waar deze hele poort tegen bedoeld is, en hij zat in de poort zelf.
-- Nu moeten ALLE cellen van een variabele vergelijkbaar zijn, met bool_and, net
-- zoals v_blocking_vars het al deed.
create or replace view v_readiness as
with cells as (
  select subject_type as tier, variable, quality, comparable
  from v_observation_current
  where not derived
), pervar as (
  select tier, variable, bool_and(coalesce(comparable, false)) as comparable
  from cells group by tier, variable
), telling as (
  select tier,
         count(*)                                  as cells,
         count(*) filter (where quality <> 'mis')  as present,
         count(*) filter (where quality = 'ver')   as verified
  from cells group by tier
), variabelen as (
  select tier, count(*) as vars, count(*) filter (where comparable) as vars_comparable
  from pervar group by tier
)
select t.tier, t.cells, t.present, t.verified, v.vars, v.vars_comparable,
       round(100.0 * t.verified / nullif(t.present,0))          as reliable_pct,
       round(100.0 * v.vars_comparable / nullif(v.vars,0))      as comparable_pct,
       round(100.0 * t.present / nullif(t.cells,0))             as complete_pct,
       (round(100.0*t.verified/nullif(t.present,0)) >= 80
        and round(100.0*v.vars_comparable/nullif(v.vars,0)) >= 100
        and round(100.0*t.present/nullif(t.cells,0)) >= 95)     as gate_open
from telling t join variabelen v using (tier);

create or replace view v_blocking_vars as
select subject_type as tier, variable,
       count(*) as cells,
       count(*) filter (where quality='ver') as verified,
       bool_and(coalesce(comparable,false)) as comparable,
       string_agg(distinct coalesce(note,''), ' | ') filter (where note is not null) as notes
from v_observation_current
where not derived
group by subject_type, variable
having not bool_and(coalesce(comparable,false))
    or count(*) filter (where quality='ver') < count(*);

-- Hoeveel gemeenten halen welke neerslagdrempel? Een view en geen getal, want de
-- ondergrens is een keuze en geen eigenschap: 450 mm hoort bij dehesa-herstel,
-- 500 bij Atlantisch loofbos, en daarboven wordt het een ander project.
create or replace view v_rain_thresholds as
select t.mm as drempel,
       count(*) filter (where o.value_num >= t.mm)                    as gemeenten,
       round(100.0 * count(*) filter (where o.value_num >= t.mm) / nullif(count(*),0)) as pct,
       count(*)                                                        as gemeten
from (values (400),(450),(500),(550),(600),(700),(800)) as t(mm)
cross join v_observation_current o
where o.subject_type='municipality' and o.variable='rain_mm'
group by t.mm order by t.mm;
