#!/bin/sh
set -eu

# Read the full v2 API token written by the superuser-sync service.
if [ -f /token-store/api_token ]; then
  export NETBOX_TOKEN="$(cat /token-store/api_token)"
elif [ -f /run/secrets/superuser_api_token ]; then
  export NETBOX_TOKEN="$(cat /run/secrets/superuser_api_token)"
else
  echo "ERROR: No API token found in /token-store/ or /run/secrets/" >&2
  exit 1
fi

echo "Starting netbox-geo-foss geographic import..."
exec python /opt/geo-foss/import-geo-data.py
