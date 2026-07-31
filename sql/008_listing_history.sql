-- Een advertentie is een waarneming, geen object.
--
-- Dezelfde finca kan drie keer op een portal staan met drie prijzen. Wie de laatste
-- overschrijft, gooit weg dat de vraagprijs in vier maanden met twintig procent
-- zakte, en dat is precies het soort informatie waarvoor je een dataset bijhoudt.
--
-- Vandaar een sleutel op (listing_url, seen_at): dezelfde advertentie op een nieuwe
-- kijkdatum is een nieuwe rij, dezelfde advertentie op dezelfde dag is een dubbele
-- inname en verandert niets.
create unique index if not exists parcel_listing_seen_ix
  on parcel (listing_url, seen_at) where kind = 'listing';

-- Prijsverloop per advertentie, voor zover we hem meer dan eens gezien hebben.
create or replace view v_listing_history as
select listing_url, muni_name, region_code,
       count(*)                                   as waarnemingen,
       min(seen_at)                               as eerst_gezien,
       max(seen_at)                               as laatst_gezien,
       min(price_eur)                             as laagste,
       max(price_eur)                             as hoogste,
       round(100.0 * (max(price_eur) - min(price_eur)) / nullif(max(price_eur), 0))
                                                  as spreiding_pct
from parcel where kind = 'listing' and listing_url is not null
group by listing_url, muni_name, region_code
having count(*) > 1
order by spreiding_pct desc nulls last;
