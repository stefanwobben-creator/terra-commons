#!/usr/bin/env bash
# PostgreSQL met PostGIS op een GitHub-runner, zonder Docker.
#
# Aanleiding: het ophalen van postgis/postgis:16-3.4 liep vast op Docker Hub
# ("context deadline exceeded"). Dat is geen fout in dit project, maar wel een
# afhankelijkheid die we niet nodig hebben: de runner heeft PostgreSQL al aan
# boord, en PostGIS is een apt-pakket van twintig seconden. Een bouwstap minder
# die kan omvallen door iets buiten ons.
set -euo pipefail

echo "== PostgreSQL starten"
sudo systemctl start postgresql 2>/dev/null || sudo service postgresql start

VER=$(ls /usr/lib/postgresql 2>/dev/null | sort -n | tail -1)
if [ -z "${VER}" ]; then
  echo "geen PostgreSQL gevonden, installeren"
  sudo apt-get update -qq
  sudo apt-get install -y -qq postgresql postgresql-client
  VER=$(ls /usr/lib/postgresql | sort -n | tail -1)
fi
echo "   versie ${VER}"

if [ ! -f "/usr/share/postgresql/${VER}/extension/postgis.control" ]; then
  echo "== PostGIS installeren"
  sudo apt-get update -qq
  sudo apt-get install -y -qq "postgresql-${VER}-postgis-3"
fi

sudo systemctl restart postgresql 2>/dev/null || sudo service postgresql restart
for i in $(seq 1 30); do
  pg_isready -q && break
  sleep 1
done
pg_isready

echo "== rol en database"
sudo -u postgres psql -q -c "do \$\$ begin
  if not exists (select 1 from pg_roles where rolname='terra') then
    create role terra login password 'terra' superuser;
  end if; end \$\$;"
sudo -u postgres psql -tAc "select 1 from pg_database where datname='terra'" | grep -q 1 \
  || sudo -u postgres createdb -O terra terra

psql "postgresql://terra:terra@127.0.0.1:5432/terra" -tAc \
  "create extension if not exists postgis; select postgis_version()"
echo "== klaar"
