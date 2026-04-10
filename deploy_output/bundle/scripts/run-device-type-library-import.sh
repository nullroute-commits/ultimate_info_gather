#!/bin/sh
set -eu

attempt=1
while [ "$attempt" -le 60 ]; do
  if /opt/netbox/venv/bin/python - <<'PY'
import os
import sys
from urllib.error import URLError
from urllib.request import urlopen

url = os.environ["NETBOX_URL"].rstrip("/") + "/login/"

try:
    with urlopen(url, timeout=10) as response:
        sys.exit(0 if response.status == 200 else 1)
except URLError:
    sys.exit(1)
PY
  then
    break
  fi

  if [ "$attempt" -eq 60 ]; then
    echo "NetBox service did not become ready in time" >&2
    exit 1
  fi

  attempt=$((attempt + 1))
  sleep 2
done

exec /opt/netbox/venv/bin/python -u /opt/netbox/import-scripts/import-device-type-library.py
