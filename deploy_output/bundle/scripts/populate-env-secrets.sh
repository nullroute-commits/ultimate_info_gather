#!/bin/sh
# populate-env-secrets.sh
# Reads the generated secrets/ files and rewrites env/diode.env with the real
# values. Run this once after populating secrets/ and before `docker compose up`.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS_DIR="$SCRIPT_DIR/secrets"
DIODE_ENV="$SCRIPT_DIR/env/diode.env"

read_secret() { cat "$SECRETS_DIR/$1" | tr -d '\n'; }

redis_pw="$(read_secret diode_redis_password)"
pg_pw="$(read_secret db_password)"
netbox_to_diode="$(read_secret netbox_to_diode)"

sed -i \
    -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${redis_pw}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pg_pw}|" \
    -e "s|^DIODE_TO_NETBOX_CLIENT_SECRET=.*|DIODE_TO_NETBOX_CLIENT_SECRET=${netbox_to_diode}|" \
    "$DIODE_ENV"

echo "env/diode.env updated with real secret values."
