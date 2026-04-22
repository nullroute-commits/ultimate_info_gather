#!/bin/sh
# populate-env-secrets.sh
# Reads the generated secrets/ files and rewrites env/diode.env with the real
# values. Run this once after populating secrets/ and before `docker compose up`.
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SECRETS_DIR="$SCRIPT_DIR/secrets"
DIODE_ENV="$SCRIPT_DIR/env/diode.env"
ORB_AGENT_YAML="$SCRIPT_DIR/configuration/orb/agent.yaml"

read_secret() { cat "$SECRETS_DIR/$1" | tr -d '\n'; }

redis_pw="$(read_secret diode_redis_password)"
pg_pw="$(read_secret db_password)"
netbox_to_diode="$(read_secret netbox_to_diode)"
diode_client_secret="$(read_secret diode_client_secret)"

sed -i \
    -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=${redis_pw}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${pg_pw}|" \
    -e "s|^DIODE_TO_NETBOX_CLIENT_SECRET=.*|DIODE_TO_NETBOX_CLIENT_SECRET=${netbox_to_diode}|" \
    "$DIODE_ENV"

echo "env/diode.env updated with real secret values."

# The ORB agent reads its OAuth2 client_secret directly from agent.yaml
# (no _FILE pattern available). Substitute the placeholder before first start.
if [ -f "$ORB_AGENT_YAML" ]; then
    sed -i \
        -e "s|client_secret: replace-me|client_secret: ${diode_client_secret}|" \
        "$ORB_AGENT_YAML"
    echo "configuration/orb/agent.yaml updated with real diode_client_secret."
fi
