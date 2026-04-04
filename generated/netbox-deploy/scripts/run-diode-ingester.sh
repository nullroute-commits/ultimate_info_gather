#!/bin/sh
set -eu

export REDIS_PASSWORD="$(cat /run/secrets/diode_redis_password)"
exec /usr/local/bin/diode-server
