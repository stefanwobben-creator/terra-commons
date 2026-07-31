-- Focus op Spanje.
--
-- Waarom dit een kolom is en geen delete: het onderzoek naar Portugal, Roemenie,
-- Italie en Bulgarije is echt gedaan en blijft staan. Wat verandert is dat die
-- dossiers de rijpheidspoort niet langer gijzelen.
--
-- Concreet probleem dat dit oplost: Roemenie, Italie en Bulgarije zijn in dit
-- model geen NUTS2-regio's maar dossiers over meerdere regio's. Ze kunnen dus
-- nooit gemeenten krijgen, en daarmee ook nooit een rastergemeten neerslag. Zolang
-- ze meetellen in de noemer kan de vergelijkbaarheid per definitie niet naar 100.
-- Dat is geen datakwaliteitsprobleem maar een scopeprobleem, en het hoort ook zo
-- opgelost te worden.

alter table country add column if not exists in_scope boolean not null default true;
alter table country add column if not exists scope_note text;

-- Alles wat binnen de scope valt, per laag. Een gemeente erft de scope van haar
-- regio, een regio die van haar land.
create or replace view v_scope as
select 'country' as tier, c.code as subject_id from country c where c.in_scope
union all
select 'region', r.code from region r join country c on c.code = r.country_code
  where c.in_scope
union all
select 'municipality', m.code from municipality m
  join region r on r.code = m.region_code
  join country c on c.code = r.country_code where c.in_scope
union all
select 'parcel', p.id::text from parcel p
  left join region r on r.code = p.region_code
  left join country c on c.code = r.country_code where coalesce(c.in_scope, true);

create or replace view v_readiness as
with cells as (
  select o.subject_type as tier, o.variable, o.quality, o.comparable
  from v_observation_current o
  join v_scope s on s.tier = o.subject_type and s.subject_id = o.subject_id
  where not o.derived
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
select o.subject_type as tier, o.variable,
       count(*) as cells,
       count(*) filter (where o.quality='ver') as verified,
       bool_and(coalesce(o.comparable,false)) as comparable,
       string_agg(distinct coalesce(o.note,''), ' | ') filter (where o.note is not null) as notes
from v_observation_current o
join v_scope s on s.tier = o.subject_type and s.subject_id = o.subject_id
where not o.derived
group by o.subject_type, o.variable
having not bool_and(coalesce(o.comparable,false))
    or count(*) filter (where o.quality='ver') < count(*);

-- Wat er buiten de scope valt, met de reden. Zichtbaar houden, niet wegmoffelen.
create or replace view v_out_of_scope as
select c.code, c.name, c.scope_note,
       (select count(*) from region r where r.country_code = c.code) as regios
from country c where not c.in_scope order by c.code;
