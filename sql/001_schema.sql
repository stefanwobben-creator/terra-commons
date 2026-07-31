-- Terra Commons, schema v1
-- Kernidee: elke gemeten waarde draagt herkomst en kwaliteit met zich mee, zodat
-- de rijpheidspoort (betrouwbaar/vergelijkbaar/volledig) een SQL-view is en geen
-- handmatige telling. Zonder dat wordt de poort binnen een maand een leugen.

create extension if not exists postgis;

-- ---------------------------------------------------------------- bronnen
create table if not exists source (
  id            text primary key,
  name          text not null,
  url           text,
  licence       text,
  cadence       text not null,               -- 'once','annual','seasonal','weekly','nightly','on_demand'
  automatable   boolean not null,            -- false = mens nodig, geen cron
  tier          text not null,               -- country|region|municipality|parcel
  last_run      timestamptz,
  next_due      date,
  notes         text
);

-- ---------------------------------------------------------------- hierarchie
create table if not exists country (
  code            char(2) primary key,       -- ISO 3166-1
  name            text not null,
  buy_allowed     boolean,                   -- mag een EU-particulier verwerven?
  buy_conditions  text,
  use_obligation  boolean,                   -- exclusief agrarisch gebruik verplicht?
  exit_levy_pct   numeric,                   -- heffing bij doorverkoop
  exit_levy_years int,
  gate_open       boolean,                   -- stap 0: mag dit land door?
  gate_reason     text
);

create table if not exists region (
  code         text primary key,
  country_code char(2) not null references country(code),
  name         text not null,
  nuts2        text,
  geom         geometry(MultiPolygon, 3035)
);

create table if not exists municipality (
  code         text primary key,             -- LAU
  region_code  text not null references region(code),
  name         text not null,
  area_ha      numeric,
  geom         geometry(MultiPolygon, 3035)
);
create index if not exists municipality_geom_ix on municipality using gist (geom);
create index if not exists municipality_region_ix on municipality (region_code);

-- Percelen: twee soorten object, bewust in een tabel met een discriminator.
create table if not exists parcel (
  id           bigserial primary key,
  kind         text not null check (kind in ('listing','candidate')),
  muni_code    text references municipality(code),
  region_code  text references region(code),
  muni_name    text,
  ha           numeric,
  price_eur    numeric,
  refcat       text,
  listing_url  text,
  source_id    text references source(id),
  seen_at      date,
  geom         geometry(MultiPolygon, 3035)
);
create index if not exists parcel_geom_ix on parcel using gist (geom);
create index if not exists parcel_kind_ix on parcel (kind, region_code);

-- ---------------------------------------------------------------- observaties
-- Bewust een EAV-tabel: kwaliteit per cel is de eenheid waarop de poort rekent.
create table if not exists observation (
  id           bigserial primary key,
  subject_type text not null check (subject_type in ('country','region','municipality','parcel')),
  subject_id   text not null,
  variable     text not null,
  value_num    double precision,
  value_txt    text,
  unit         text,
  quality      text not null check (quality in ('ver','ind','mis')),
  comparable   boolean,
  source_id    text references source(id),
  observed_at  date not null,
  valid_until  date,
  note         text,
  unique (subject_type, subject_id, variable, observed_at)
);
create index if not exists obs_lookup_ix on observation (subject_type, variable, subject_id);

-- ---------------------------------------------------------------- criteria
create table if not exists criterion (
  k             text primary key,
  category      text not null check (category in ('gate','cond','score')),
  scope         text not null,
  jurisdiction  text,
  intent_dep    boolean not null default false,
  threshold     jsonb,
  label_nl      text, label_en text,
  why_nl        text, why_en  text
);

-- ---------------------------------------------------------------- besluiten
create table if not exists promotion (
  tier        text not null,
  subject_id  text not null,
  status      text not null check (status in ('promoted','rejected','pending')),
  reasons     jsonb,
  decided_at  timestamptz not null default now(),
  run_id      bigint,
  primary key (tier, subject_id, decided_at)
);

create table if not exists run (
  id          bigserial primary key,
  task        text not null,
  tier        text,
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  ok          boolean,
  stats       jsonb,
  error       text
);
