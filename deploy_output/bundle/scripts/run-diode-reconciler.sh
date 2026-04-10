#!/bin/sh
set -eu

export REDIS_PASSWORD="$(cat /run/secrets/diode_redis_password)"
export POSTGRES_PASSWORD="$(cat /run/secrets/db_password)"
export DIODE_TO_NETBOX_CLIENT_ID="netbox-to-diode"
export DIODE_TO_NETBOX_CLIENT_SECRET="$(cat /run/secrets/netbox_to_diode)"
exec /usr/local/bin/diode-server
