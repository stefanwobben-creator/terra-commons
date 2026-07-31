-- Herkomst is niet optioneel.
--
-- Aanleiding: van de dertig advertenties in de eerste longlist had er geen enkele
-- een URL of een kijkdatum. Daarmee was geen ervan na te lopen, in precies het
-- systeem dat herkomst zou bijhouden. Deze constraint maakt die fout onmogelijk
-- in plaats van onwaarschijnlijk.

alter table parcel drop constraint if exists parcel_listing_provenance;
alter table parcel add constraint parcel_listing_provenance check (
  kind <> 'listing'
  or (listing_url is not null and seen_at is not null and source_id is not null)
);

-- Wat er niet in mag, gooien we niet weg: het gaat in quarantaine, met de reden
-- erbij. Een lege tabel liegt niet, een stilzwijgend genegeerde rij wel.
create table if not exists listing_quarantine (
  id           bigserial primary key,
  region_code  text,
  muni_name    text,
  ha           numeric,
  price_eur    numeric,
  src_name     text,
  reason       text not null,
  intake_at    timestamptz not null default now(),
  raw          jsonb
);

-- Wat de trechter zou doen zodra de herkomst er is. Expliciet een 'zou',
-- daarom een aparte view en niet v_funnel.
create or replace view v_quarantine_report as
select region_code,
       count(*)                                             as n,
       count(*) filter (where ha between 20 and 90)          as profile_fit,
       count(*) filter (where ha > 100)                      as over_100ha,
       round(percentile_cont(0.5) within group (order by price_eur/nullif(ha,0))) as median_eur_ha,
       min(reason)                                           as reason
from listing_quarantine
group by region_code
order by n desc;
