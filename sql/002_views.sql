-- Views die de inzichten uitvoerbaar maken.

-- 1. De rijpheidspoort per tier. Dezelfde rekensom als op de site, maar afgeleid
--    uit de database, zodat hij meebeweegt zodra er data bijkomt.
create or replace view v_readiness as
with cells as (
  select subject_type as tier, variable, quality, comparable
  from observation
), agg as (
  select tier,
         count(*)                                            as cells,
         count(*) filter (where quality <> 'mis')            as present,
         count(*) filter (where quality = 'ver')             as verified,
         count(distinct variable)                            as vars,
         count(distinct variable) filter (where comparable)   as vars_comparable
  from cells group by tier
)
select tier, cells, present, verified, vars, vars_comparable,
       round(100.0 * verified / nullif(present,0))            as reliable_pct,
       round(100.0 * vars_comparable / nullif(vars,0))        as comparable_pct,
       round(100.0 * present / nullif(cells,0))               as complete_pct,
       (round(100.0*verified/nullif(present,0)) >= 80
        and round(100.0*vars_comparable/nullif(vars,0)) >= 100
        and round(100.0*present/nullif(cells,0)) >= 95)       as gate_open
from agg;

-- 2. Welke variabelen blokkeren de vergelijkbaarheidseis, met de reden erbij.
create or replace view v_blocking_vars as
select subject_type as tier, variable,
       count(*) as cells,
       count(*) filter (where quality='ver') as verified,
       bool_and(coalesce(comparable,false)) as comparable,
       string_agg(distinct coalesce(note,''), ' | ') filter (where note is not null) as notes
from observation
group by subject_type, variable
having not bool_and(coalesce(comparable,false))
    or count(*) filter (where quality='ver') < count(*);

-- 3. De trechter: hoeveel subjects staan er per tier en per status.
create or replace view v_funnel as
select p.tier, p.status, count(distinct p.subject_id) as n
from promotion p
join (select tier, subject_id, max(decided_at) as latest
      from promotion group by tier, subject_id) l
  on l.tier=p.tier and l.subject_id=p.subject_id and l.latest=p.decided_at
group by p.tier, p.status;

-- 4. Handmatige schuld: bronnen die niet te automatiseren zijn en over tijd.
--    De eerlijke tegenhanger van "elke avond bijgewerkt".
create or replace view v_manual_debt as
select id, name, tier, cadence, last_run, next_due,
       (next_due is null or next_due <= current_date) as overdue
from source
where not automatable
order by overdue desc, next_due nulls first;

-- 5. Per perceel: welke criteria raken het, uitgesplitst naar poort/voorwaarde/score.
create or replace view v_parcel_criteria as
select pa.id, pa.kind, coalesce(m.name, pa.muni_name) as muni, pa.region_code,
       pa.ha, pa.price_eur,
       case when pa.ha > 0 then round(pa.price_eur / pa.ha) end as eur_per_ha,
       c.k, c.category, c.label_nl
from parcel pa
left join municipality m on m.code = pa.muni_code
join criterion c on true
where (c.jurisdiction is null or c.jurisdiction = pa.region_code);
