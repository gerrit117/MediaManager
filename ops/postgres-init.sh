#!/bin/sh
set -eu
psql --username "$POSTGRES_USER" --dbname postgres --no-psqlrc -v ON_ERROR_STOP=1 <<'SQL'
\set app_password `cat /run/secrets/app_db_password`
CREATE ROLE mediamanager LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE DATABASE mediamanager OWNER mediamanager;
SQL
