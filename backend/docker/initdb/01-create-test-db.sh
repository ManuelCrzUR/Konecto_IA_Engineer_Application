#!/bin/bash
# Runs once, on first init of the data volume (an existing volume needs
# `docker compose down -v`). Creates the test database, owned by whatever
# POSTGRES_USER is configured, so tests never touch the real one.
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -c "CREATE DATABASE \"${POSTGRES_DB}_test\" OWNER \"$POSTGRES_USER\";"
