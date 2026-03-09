"""Render deployment bundles from a deployment plan."""

from __future__ import annotations

import json
import pprint
import re
from pathlib import Path

from .models import DeploymentPlan


def _render_plugin_list(plan: DeploymentPlan) -> list[str]:
    return [plugin.module_name for plugin in plan.plugins if plugin.enabled]


def _render_plugins_config(plan: DeploymentPlan) -> dict[str, object]:
    return {
        plugin.module_name: plugin.config
        for plugin in plan.plugins
        if plugin.enabled and plugin.config
    }


def render_plugin_requirements(plan: DeploymentPlan) -> str:
    """Render plugin requirements with exact versions."""

    lines = [
        f"{plugin.package_name}=={plugin.version}"
        for plugin in plan.plugins
      if plugin.enabled or plugin.install_when_disabled
    ]
    return "\n".join(lines) + "\n"


def render_plugins_py(plan: DeploymentPlan) -> str:
    """Render NetBox plugin configuration."""

    plugins = pprint.pformat(_render_plugin_list(plan), indent=4, sort_dicts=False)
    config = pprint.pformat(_render_plugins_config(plan), indent=4, sort_dicts=True)
    return (
        '"""Generated plugin configuration for NetBox."""\n\n'
        f"PLUGINS = {plugins}\n\n"
        f"PLUGINS_CONFIG = {config}\n"
    )


def render_dockerfile_plugins(plan: DeploymentPlan) -> str:
    """Render the plugin image Dockerfile."""

    return f"""ARG NETBOX_IMAGE={plan.images.netbox_image}
FROM ${{NETBOX_IMAGE}}

COPY plugin_requirements.txt /opt/netbox/plugin_requirements.txt
RUN /usr/local/bin/uv pip install \
  --python /opt/netbox/venv/bin/python \
  -r /opt/netbox/plugin_requirements.txt

COPY configuration/plugins.py /etc/netbox/config/plugins.py
RUN mkdir -p /opt/netbox/netbox/static/netbox_topology_views/img
RUN SECRET_KEY=dummydummydummydummydummydummydummydummydummydummy \\
    /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py collectstatic --no-input
"""


def _render_library_archive_url(plan: DeploymentPlan) -> str:
    repository = plan.device_type_library.library_repository.removesuffix(".git")
    return f"{repository}/archive/{plan.device_type_library.library_ref}.tar.gz"


def _render_netbox_healthcheck_command() -> str:
    return (
        "from urllib.request import urlopen; import sys; "
        "response = urlopen('http://127.0.0.1:8080/login/', timeout=10); "
        "sys.exit(0 if response.status == 200 else 1)"
    )


def _segment_cidr(plan: DeploymentPlan, name: str) -> str:
    for segment in plan.networks.segments:
        if segment.name == name:
            return segment.cidr
    raise ValueError(f"Missing required network segment '{name}'")


def _render_network_notes(plan: DeploymentPlan) -> str:
    lines = []
    for segment in plan.networks.segments:
        lines.append(
            f"- {segment.name}: {segment.cidr} (required hosts: {segment.required_hosts})"
        )
    return "\n".join(lines)


def _render_worker_services(plan: DeploymentPlan) -> str:
    """Render one or more NetBox worker containers."""

    count = max(1, plan.sizing.netbox_worker_containers)
    blocks: list[str] = []

    for idx in range(1, count + 1):
        service_name = "netbox-worker" if idx == 1 else f"netbox-worker-{idx}"
        block = f"""  {service_name}:
    image: {plan.deployment_name}:local
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      valkey:
        condition: service_healthy
      netbox:
        condition: service_healthy
    env_file:
      - env/netbox.env
    secrets:
      - db_password
      - api_token_pepper_1
      - secret_key
      - superuser_name
      - superuser_password
      - superuser_api_token
    command: ["/opt/netbox/venv/bin/python", "/opt/netbox/netbox/manage.py", "rqworker"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp
    networks:
      - data
"""
        blocks.append(block)

    return "\n".join(blocks).rstrip()


def render_compose(plan: DeploymentPlan) -> str:
    """Render a standalone compose file aligned to netbox-docker conventions."""

    edge_cidr = _segment_cidr(plan, "edge")
    app_cidr = _segment_cidr(plan, "app")
    data_cidr = _segment_cidr(plan, "data")
    security_cidr = _segment_cidr(plan, "security")

    return f"""services:
  traefik-certgen:
    image: alpine/openssl:latest
    restart: "no"
    entrypoint: ["/bin/sh"]
    command: ["/opt/scripts/generate-traefik-cert.sh"]
    volumes:
      - traefik-certs:/certs
      - ./scripts:/opt/scripts:ro
    networks:
      - edge

  traefik:
    image: traefik:v3.2
    restart: unless-stopped
    depends_on:
      traefik-certgen:
        condition: service_completed_successfully
      waf:
        condition: service_started
    command:
      - --api.dashboard=false
      - --ping=true
      - --providers.file.directory=/etc/traefik/dynamic
      - --entrypoints.websecure.address=:443
      - --log.level=INFO
    ports:
      - "443:443"
    volumes:
      - traefik-certs:/certs:ro
      - ./configuration/traefik:/etc/traefik/dynamic:ro
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://127.0.0.1:8080/ping"]
      interval: 15s
      timeout: 5s
      retries: 10
    networks:
      - edge
      - app

  waf:
    image: owasp/modsecurity-crs:nginx
    restart: unless-stopped
    depends_on:
      netbox:
        condition: service_healthy
    volumes:
      - ./configuration/waf/default.conf:/etc/nginx/templates/conf.d/default.conf.template:ro
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s
      timeout: 5s
      retries: 5
    networks:
      - app
      - data

  postgres:
    image: {plan.images.postgres_image}
    restart: unless-stopped
    entrypoint:
      - /bin/sh
      - -c
      - |
        export POSTGRES_PASSWORD="$(cat /run/secrets/db_password)"
        unset POSTGRES_PASSWORD_FILE
        exec docker-entrypoint.sh postgres
    env_file:
      - env/postgres.env
    secrets:
      - db_password
    volumes:
      - postgres-data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 15s
      timeout: 5s
      retries: 10
    networks:
      - data

  valkey:
    image: {plan.images.valkey_image}
    restart: unless-stopped
    command: ["valkey-server", "--appendonly", "yes"]
    volumes:
      - valkey-data:/data
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 15s
      timeout: 5s
      retries: 10
    networks:
      - data

  diode:
    image: netboxlabs/diode-auth:latest
    restart: unless-stopped
    networks:
      - data

  netbox:
    build:
      context: .
      dockerfile: Dockerfile-Plugins
      args:
        NETBOX_IMAGE: {plan.images.netbox_image}
    image: {plan.deployment_name}:local
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      valkey:
        condition: service_healthy
      diode:
        condition: service_started
    env_file:
      - env/netbox.env
    secrets:
      - db_password
      - api_token_pepper_1
      - secret_key
      - superuser_name
      - superuser_password
      - superuser_api_token
    healthcheck:
      test:
        [
          "CMD",
          "/opt/netbox/venv/bin/python",
          "-c",
          "{_render_netbox_healthcheck_command()}",
        ]
      interval: 15s
      timeout: 10s
      retries: 12
      start_period: 8m
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp
    volumes:
      - netbox-media:/opt/netbox/netbox/media
      - netbox-reports:/etc/netbox/reports
      - netbox-scripts:/etc/netbox/scripts
    networks:
      - data

{_render_worker_services(plan)}

  netbox-superuser-sync:
    image: {plan.deployment_name}:local
    restart: "no"
    depends_on:
      netbox:
        condition: service_healthy
    env_file:
      - env/netbox.env
    secrets:
      - db_password
      - api_token_pepper_1
      - secret_key
      - superuser_name
      - superuser_password
      - superuser_api_token
    command: ["/bin/sh", "/opt/netbox/bootstrap/sync-superuser.sh"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp
    volumes:
      - ./scripts:/opt/netbox/bootstrap:ro
      - token-store:/token-store
    networks:
      - data

  {plan.device_type_library.import_service_name}:
    profiles: ["device-type-library-import"]
    image: {plan.deployment_name}:local
    restart: "no"
    depends_on:
      netbox:
        condition: service_healthy
    env_file:
      - env/netbox.env
      - env/device-type-library-import.env
    secrets:
      - db_password
      - api_token_pepper_1
      - secret_key
      - superuser_name
      - superuser_password
      - superuser_api_token
    command: ["/bin/sh", "/opt/netbox/import-scripts/run-device-type-library-import.sh"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    user: "${{LOCAL_UID:-1000}}:${{LOCAL_GID:-1000}}"
    tmpfs:
      - /tmp
    volumes:
      - ./scripts:/opt/netbox/import-scripts:ro
    networks:
      - data

  {plan.geo_foss.service_name}:
    profiles: ["geo-foss-import"]
    build:
      context: .
      dockerfile: Dockerfile-GeoFoss
    image: {plan.deployment_name}-geo-foss:local
    restart: "no"
    depends_on:
      netbox:
        condition: service_healthy
      netbox-superuser-sync:
        condition: service_completed_successfully
    env_file:
      - env/geo-foss.env
    secrets:
      - superuser_api_token
    command: ["/bin/sh", "/opt/geo-foss/run-geo-foss-import.sh"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp
    volumes:
      - geo-foss-cache:/app/cache
      - ./scripts:/opt/geo-foss:ro
      - token-store:/token-store:ro
    networks:
      - data

  wazuh-agent:
    image: wazuh/wazuh-agent:4.14.3
    profiles: ["security-observability"]
    restart: unless-stopped
    environment:
      WAZUH_MANAGER: "wazuh-manager"
      WAZUH_AGENT_NAME: "{plan.deployment_name}-wazuh-agent"
    networks:
      - security

  orb-agent:
    image: {plan.deployment_name}:local
    restart: unless-stopped
    depends_on:
      netbox:
        condition: service_healthy
      netbox-superuser-sync:
        condition: service_completed_successfully
    env_file:
      - env/orb.env
    secrets:
      - superuser_api_token
    command: ["/bin/sh", "/opt/netbox/bootstrap/run-orb-agent.sh"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp
    volumes:
      - ./configuration/orb:/etc/netbox/config/orb:ro
      - ./scripts:/opt/netbox/bootstrap:ro
    networks:
      - data

secrets:
  db_password:
    file: secrets/db_password
  api_token_pepper_1:
    file: secrets/api_token_pepper_1
  secret_key:
    file: secrets/secret_key
  superuser_name:
    file: secrets/superuser_name
  superuser_password:
    file: secrets/superuser_password
  superuser_api_token:
    file: secrets/superuser_api_token

volumes:
  traefik-certs:
  postgres-data:
  valkey-data:
  netbox-media:
  netbox-reports:
  netbox-scripts:
  geo-foss-cache:
  token-store:

networks:
  edge:
    driver: bridge
    ipam:
      config:
        - subnet: {edge_cidr}
  app:
    driver: bridge
    ipam:
      config:
        - subnet: {app_cidr}
  data:
    driver: bridge
    ipam:
      config:
        - subnet: {data_cidr}
  security:
    driver: bridge
    ipam:
      config:
        - subnet: {security_cidr}
"""


def render_netbox_env(plan: DeploymentPlan) -> str:
    """Render the NetBox application environment."""

    return f"""ALLOWED_HOSTS=localhost 127.0.0.1 netbox traefik waf {plan.host.hostname}
CSRF_TRUSTED_ORIGINS=https://localhost https://{plan.host.hostname}
DB_HOST=postgres
DB_NAME=netbox
DB_PORT=5432
DB_USER=netbox
DB_PASSWORD_FILE=/run/secrets/db_password
METRICS_ENABLED=true
REDIS_CACHE_HOST=valkey
REDIS_CACHE_PORT=6379
REDIS_HOST=valkey
REDIS_PORT=6379
RELEASE_CHECK_URL=
SECRET_KEY_FILE=/run/secrets/secret_key
SKIP_SUPERUSER=false
SUPERUSER_NAME={plan.admin_privacy.bootstrap_username}
SUPERUSER_EMAIL={plan.admin_privacy.bootstrap_email}
WEB_CONCURRENCY={plan.sizing.netbox_workers}
"""


def render_postgres_env(plan: DeploymentPlan) -> str:
    """Render the PostgreSQL environment."""

    return f"""POSTGRES_DB=netbox
POSTGRES_USER=netbox
POSTGRES_PASSWORD_FILE=/run/secrets/db_password
PG_SHARED_BUFFERS={plan.sizing.postgres_shared_buffers}
PG_MAX_CONNECTIONS={plan.sizing.postgres_max_connections}
"""


def render_traefik_dynamic_config() -> str:
    """Render Traefik dynamic config for TLS certs and compression middleware."""

    return """tls:
  certificates:
    - certFile: /certs/tls.crt
      keyFile: /certs/tls.key

http:
  routers:
    netbox:
      rule: "PathPrefix(`/`)"
      entryPoints:
        - websecure
      tls: {}
      service: netbox-waf
      middlewares:
        - netbox-compress

  services:
    netbox-waf:
      loadBalancer:
        servers:
          - url: "http://waf:8081"

  middlewares:
    netbox-compress:
      compress: {}
"""


def render_waf_default_conf() -> str:
    """Render the WAF sidecar reverse proxy config."""

    return """server {
    listen 8081;
    server_name _;

    location / {
        proxy_pass http://netbox:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port 443;
    }
}
"""


def render_traefik_cert_script(plan: DeploymentPlan) -> str:
    """Render a bootstrap script that generates a self-signed certificate."""

    san_entries = [
        "DNS:localhost",
        "DNS:traefik",
        "DNS:netbox",
        "IP:127.0.0.1",
    ]
    hostname = plan.host.hostname.strip()
    if hostname and re.fullmatch(
        r"[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*",
        hostname,
    ):
        hostname_entry = f"DNS:{hostname}"
        if hostname_entry not in san_entries:
            san_entries.append(hostname_entry)

    return """#!/bin/sh
set -eu

if [ -s /certs/tls.crt ] && [ -s /certs/tls.key ]; then
  exit 0
fi

openssl req \
  -x509 \
  -nodes \
  -days 365 \
  -newkey rsa:4096 \
  -subj '/CN=localhost' \
  -addext 'subjectAltName=""" + ",".join(san_entries) + """' \
  -keyout /certs/tls.key \
  -out /certs/tls.crt
chmod 600 /certs/tls.key
chmod 644 /certs/tls.crt
"""


def render_superuser_sync_script() -> str:
  """Render a one-shot helper that enforces secret-backed superuser credentials."""

  return """#!/bin/sh
set -eu

if [ ! -f /run/secrets/superuser_name ] || [ ! -f /run/secrets/superuser_password ]; then
  echo "Missing required superuser secret files" >&2
  exit 1
fi

NB_SUPERUSER_NAME="$(cat /run/secrets/superuser_name)"
NB_SUPERUSER_PASSWORD="$(cat /run/secrets/superuser_password)"
NB_SUPERUSER_API_TOKEN=""
if [ -f /run/secrets/superuser_api_token ]; then
  NB_SUPERUSER_API_TOKEN="$(cat /run/secrets/superuser_api_token)"
fi

export NB_SUPERUSER_NAME NB_SUPERUSER_PASSWORD NB_SUPERUSER_API_TOKEN
/opt/netbox/venv/bin/python -u /opt/netbox/netbox/manage.py shell <<'PY'
from django.contrib.auth import get_user_model
import os

username = os.environ["NB_SUPERUSER_NAME"].strip()
password = os.environ["NB_SUPERUSER_PASSWORD"]
api_token_key = os.environ.get("NB_SUPERUSER_API_TOKEN", "").strip()

if not username:
  raise RuntimeError("Superuser name secret is empty")

user_model = get_user_model()
user, created = user_model.objects.get_or_create(
  username=username,
  defaults={"is_superuser": True, "is_active": True},
)

changed = created
if not user.is_superuser:
  user.is_superuser = True
  changed = True
if not user.is_active:
  user.is_active = True
  changed = True
if not user.check_password(password):
  user.set_password(password)
  changed = True

if changed:
  user.save()

# Ensure a v2 API token exists for this user
if api_token_key:
  from django.conf import settings
  from users.models import Token
  from users.choices import TokenVersionChoices
  if settings.API_TOKEN_PEPPERS:
    existing = None
    for t in Token.objects.filter(user=user):
      if t.validate(api_token_key):
        existing = t
        break
    if not existing:
      Token.objects.filter(user=user).delete()
      t = Token.objects.create(user=user, token=api_token_key, version=TokenVersionChoices.V2)
      changed = True
      print(f"superuser-sync: created v2 token key={t.key}")
    else:
      t = existing
      print(f"superuser-sync: token already exists key={existing.key}")

    # Write the full v2 token (nbt_<key>.<plaintext>) for sidecar services
    full_token = f"nbt_{t.key}.{api_token_key}"
    from pathlib import Path
    token_store = Path("/token-store")
    if token_store.is_dir():
      (token_store / "api_token").write_text(full_token)
      print("superuser-sync: wrote full v2 token to /token-store/api_token")

print(f"superuser-sync: username={user.username} changed={changed}")
PY
"""


def render_orb_orchestration_config(plan: DeploymentPlan) -> str:
    """Render container orchestration metadata for worker deployment."""

    worker_services = [
        "netbox-worker" if idx == 1 else f"netbox-worker-{idx}"
        for idx in range(1, max(1, plan.sizing.netbox_worker_containers) + 1)
    ]
    worker_service_yaml = "\n".join(f"      - {name}" for name in worker_services)
    enabled_plugins = [plugin.module_name for plugin in plan.plugins if plugin.enabled]
    plugin_yaml = "\n".join(f"      - {name}" for name in enabled_plugins)

    return f"""orb:
  version: 1
  deployment_name: {plan.deployment_name}
  netbox:
    url: http://netbox:8080
    api_token_file: /run/secrets/superuser_api_token
  orchestration:
    runtime: docker-compose
    worker_containers: {max(1, plan.sizing.netbox_worker_containers)}
    rollout_order:
      - postgres
      - valkey
      - netbox
      - netbox-superuser-sync
      - workers
      - waf
      - traefik
    worker_services:
{worker_service_yaml}
  netbox_plugins:
{plugin_yaml}
"""


def render_orb_env() -> str:
    """Render ORB sidecar environment values."""

    return """ORB_NETBOX_URL=http://netbox:8080
ORB_NETBOX_TOKEN_FILE=/run/secrets/superuser_api_token
ORB_ORCHESTRATION_FILE=/etc/netbox/config/orb/orchestration.yml
ORB_POLL_INTERVAL_SECONDS=30
"""


def render_orb_agent_script() -> str:
    """Render an ORB sidecar entrypoint that waits for NetBox API readiness."""

    return """#!/bin/sh
set -eu

python -u - <<'PY'
import os
import time
from urllib.error import URLError
from urllib.request import urlopen


def wait_for_netbox() -> None:
    base = os.environ["ORB_NETBOX_URL"].rstrip("/")
    login_url = f"{base}/login/"
    for attempt in range(1, 61):
        try:
            with urlopen(login_url, timeout=10) as response:  # nosec B310
                if response.status == 200:
                    return
        except URLError:
            pass

        if attempt == 60:
            raise RuntimeError("NetBox did not become reachable in time")
        time.sleep(2)


def main() -> int:
    wait_for_netbox()
    poll_interval = int(os.environ.get("ORB_POLL_INTERVAL_SECONDS", "30"))
    orchestration_file = os.environ["ORB_ORCHESTRATION_FILE"]
    print("orb-agent: connected to NetBox API; starting orchestration polling")
    print(f"orb-agent: orchestration file={orchestration_file}")

    while True:
        time.sleep(max(5, poll_interval))


if __name__ == "__main__":
    raise SystemExit(main())
PY
"""


def render_device_type_library_import_env(plan: DeploymentPlan) -> str:
    """Render the env file for the device-type-library import helper."""

    return f"""NETBOX_URL=http://netbox:8080
DEVICE_TYPE_LIBRARY_VENDORS=
DEVICE_TYPE_LIBRARY_REPOSITORY={plan.device_type_library.library_repository}
DEVICE_TYPE_LIBRARY_REF={plan.device_type_library.library_ref}
DEVICE_TYPE_LIBRARY_ARCHIVE_URL={_render_library_archive_url(plan)}
NETBOX_IMPORT_USERNAME_FILE=/run/secrets/superuser_name
"""


def render_geo_foss_env(plan: DeploymentPlan) -> str:
    """Render the env file for the netbox-geo-foss companion service."""

    return f"""NETBOX_URL=http://netbox:8080
NETBOX_VERIFY_SSL=false
GEONAMES_USERNAME=demo
DATA_CACHE_DIR=/app/cache
DATA_BATCH_SIZE=1000
DATA_MIN_CITY_POPULATION=15000
APP_ENV=production
APP_DEBUG=false
"""


def render_geo_foss_import_script() -> str:
    """Render the entrypoint wrapper that reads the API token secret and runs the import."""

    return """#!/bin/sh
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
"""


def render_geo_foss_import_runner() -> str:
    """Render the Python script that imports geographic data into NetBox via pynetbox."""

    return '''#!/usr/bin/env python3
"""Import geographic data (continents, countries, cities) into NetBox.

Uses the GeoNames REST API for country/city data and creates NetBox
Regions (continent → country hierarchy) and Sites (major cities).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pynetbox


# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
NETBOX_URL = os.environ.get("NETBOX_URL", "http://netbox:8080")
NETBOX_TOKEN = os.environ["NETBOX_TOKEN"]
GEONAMES_USERNAME = os.environ.get("GEONAMES_USERNAME", "demo")
CACHE_DIR = Path(os.environ.get("DATA_CACHE_DIR", "/app/cache"))
BATCH_SIZE = int(os.environ.get("DATA_BATCH_SIZE", "1000"))
MIN_CITY_POP = int(os.environ.get("DATA_MIN_CITY_POPULATION", "15000"))

GEONAMES_API = "http://api.geonames.org"

# Continent codes → human names
CONTINENTS = {
    "AF": "Africa",
    "AS": "Asia",
    "EU": "Europe",
    "NA": "North America",
    "SA": "South America",
    "OC": "Oceania",
    "AN": "Antarctica",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _geonames_get(endpoint: str, params: dict) -> dict:
    """Call a GeoNames JSON endpoint with rate-limit back-off."""
    params["username"] = GEONAMES_USERNAME
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{GEONAMES_API}/{endpoint}?{qs}"
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or attempt < 3:
                time.sleep(2 * attempt)
                continue
            raise
    return {}


def _slug(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    import re
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:100]


def _get_or_create_region(nb, name: str, slug: str, parent_id=None):
    """Get an existing region by slug or create a new one."""
    existing = nb.dcim.regions.get(slug=slug)
    if existing:
        return existing
    data = {"name": name, "slug": slug}
    if parent_id is not None:
        data["parent"] = parent_id
    return nb.dcim.regions.create(data)


def _get_or_create_site(nb, name: str, slug: str, region_id, latitude=None, longitude=None):
    """Get an existing site by slug or create a new one."""
    existing = nb.dcim.sites.get(slug=slug)
    if existing:
        return existing
    data = {
        "name": name,
        "slug": slug,
        "region": region_id,
        "status": "planned",
    }
    if latitude is not None:
        data["latitude"] = round(latitude, 6)
    if longitude is not None:
        data["longitude"] = round(longitude, 6)
    return nb.dcim.sites.create(data)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_path(key: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{key}.json"


def _load_cache(key: str):
    p = _cache_path(key)
    if p.exists():
        return json.loads(p.read_text())
    return None


def _save_cache(key: str, data):
    p = _cache_path(key)
    p.write_text(json.dumps(data, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Embedded fallback country data (used when GeoNames API is unavailable)
# ---------------------------------------------------------------------------
FALLBACK_COUNTRIES = [
    {"countryCode": "AF", "countryName": "Afghanistan", "continent": "AS"},
    {"countryCode": "AL", "countryName": "Albania", "continent": "EU"},
    {"countryCode": "DZ", "countryName": "Algeria", "continent": "AF"},
    {"countryCode": "AR", "countryName": "Argentina", "continent": "SA"},
    {"countryCode": "AU", "countryName": "Australia", "continent": "OC"},
    {"countryCode": "AT", "countryName": "Austria", "continent": "EU"},
    {"countryCode": "BD", "countryName": "Bangladesh", "continent": "AS"},
    {"countryCode": "BE", "countryName": "Belgium", "continent": "EU"},
    {"countryCode": "BR", "countryName": "Brazil", "continent": "SA"},
    {"countryCode": "BG", "countryName": "Bulgaria", "continent": "EU"},
    {"countryCode": "CA", "countryName": "Canada", "continent": "NA"},
    {"countryCode": "CL", "countryName": "Chile", "continent": "SA"},
    {"countryCode": "CN", "countryName": "China", "continent": "AS"},
    {"countryCode": "CO", "countryName": "Colombia", "continent": "SA"},
    {"countryCode": "HR", "countryName": "Croatia", "continent": "EU"},
    {"countryCode": "CZ", "countryName": "Czechia", "continent": "EU"},
    {"countryCode": "DK", "countryName": "Denmark", "continent": "EU"},
    {"countryCode": "EG", "countryName": "Egypt", "continent": "AF"},
    {"countryCode": "ET", "countryName": "Ethiopia", "continent": "AF"},
    {"countryCode": "FI", "countryName": "Finland", "continent": "EU"},
    {"countryCode": "FR", "countryName": "France", "continent": "EU"},
    {"countryCode": "DE", "countryName": "Germany", "continent": "EU"},
    {"countryCode": "GH", "countryName": "Ghana", "continent": "AF"},
    {"countryCode": "GR", "countryName": "Greece", "continent": "EU"},
    {"countryCode": "HK", "countryName": "Hong Kong", "continent": "AS"},
    {"countryCode": "HU", "countryName": "Hungary", "continent": "EU"},
    {"countryCode": "IN", "countryName": "India", "continent": "AS"},
    {"countryCode": "ID", "countryName": "Indonesia", "continent": "AS"},
    {"countryCode": "IR", "countryName": "Iran", "continent": "AS"},
    {"countryCode": "IQ", "countryName": "Iraq", "continent": "AS"},
    {"countryCode": "IE", "countryName": "Ireland", "continent": "EU"},
    {"countryCode": "IL", "countryName": "Israel", "continent": "AS"},
    {"countryCode": "IT", "countryName": "Italy", "continent": "EU"},
    {"countryCode": "JP", "countryName": "Japan", "continent": "AS"},
    {"countryCode": "KE", "countryName": "Kenya", "continent": "AF"},
    {"countryCode": "KR", "countryName": "South Korea", "continent": "AS"},
    {"countryCode": "MY", "countryName": "Malaysia", "continent": "AS"},
    {"countryCode": "MX", "countryName": "Mexico", "continent": "NA"},
    {"countryCode": "MA", "countryName": "Morocco", "continent": "AF"},
    {"countryCode": "NL", "countryName": "Netherlands", "continent": "EU"},
    {"countryCode": "NZ", "countryName": "New Zealand", "continent": "OC"},
    {"countryCode": "NG", "countryName": "Nigeria", "continent": "AF"},
    {"countryCode": "NO", "countryName": "Norway", "continent": "EU"},
    {"countryCode": "PK", "countryName": "Pakistan", "continent": "AS"},
    {"countryCode": "PE", "countryName": "Peru", "continent": "SA"},
    {"countryCode": "PH", "countryName": "Philippines", "continent": "AS"},
    {"countryCode": "PL", "countryName": "Poland", "continent": "EU"},
    {"countryCode": "PT", "countryName": "Portugal", "continent": "EU"},
    {"countryCode": "RO", "countryName": "Romania", "continent": "EU"},
    {"countryCode": "RU", "countryName": "Russia", "continent": "EU"},
    {"countryCode": "SA", "countryName": "Saudi Arabia", "continent": "AS"},
    {"countryCode": "SG", "countryName": "Singapore", "continent": "AS"},
    {"countryCode": "ZA", "countryName": "South Africa", "continent": "AF"},
    {"countryCode": "ES", "countryName": "Spain", "continent": "EU"},
    {"countryCode": "SE", "countryName": "Sweden", "continent": "EU"},
    {"countryCode": "CH", "countryName": "Switzerland", "continent": "EU"},
    {"countryCode": "TW", "countryName": "Taiwan", "continent": "AS"},
    {"countryCode": "TH", "countryName": "Thailand", "continent": "AS"},
    {"countryCode": "TR", "countryName": "Turkey", "continent": "EU"},
    {"countryCode": "UA", "countryName": "Ukraine", "continent": "EU"},
    {"countryCode": "AE", "countryName": "United Arab Emirates", "continent": "AS"},
    {"countryCode": "GB", "countryName": "United Kingdom", "continent": "EU"},
    {"countryCode": "US", "countryName": "United States", "continent": "NA"},
    {"countryCode": "VN", "countryName": "Vietnam", "continent": "AS"},
]


# ---------------------------------------------------------------------------
# Import steps
# ---------------------------------------------------------------------------
def fetch_countries() -> list[dict]:
    """Fetch country info from GeoNames (cached), with embedded fallback."""
    cached = _load_cache("countries")
    if cached:
        print(f"  Using cached country data ({len(cached)} countries)")
        return cached

    print("  Fetching country list from GeoNames...")
    data = _geonames_get("countryInfoJSON", {})
    countries = data.get("geonames", [])
    if countries:
        _save_cache("countries", countries)
        print(f"  Retrieved {len(countries)} countries")
    else:
        if "status" in data:
            print(f"  GeoNames API error: {data['status'].get('message', 'unknown')}")
        print(f"  Using embedded fallback ({len(FALLBACK_COUNTRIES)} countries)")
        countries = FALLBACK_COUNTRIES
        _save_cache("countries", countries)
    return countries


def fetch_cities(country_code: str, max_rows: int = 50) -> list[dict]:
    """Fetch major cities for a country from GeoNames (cached)."""
    cache_key = f"cities_{country_code}"
    cached = _load_cache(cache_key)
    if cached is not None:
        return cached

    data = _geonames_get("searchJSON", {
        "country": country_code,
        "featureClass": "P",
        "orderby": "population",
        "maxRows": str(max_rows),
        "style": "MEDIUM",
    })
    cities = [
        c for c in data.get("geonames", [])
        if int(c.get("population", 0)) >= MIN_CITY_POP
    ]
    _save_cache(cache_key, cities)
    return cities


def import_continents(nb) -> dict[str, int]:
    """Create continent-level regions. Returns {code: region_id}."""
    print("\\n=== Importing continents as top-level regions ===")
    mapping = {}
    for code, name in CONTINENTS.items():
        region = _get_or_create_region(nb, name, _slug(name))
        mapping[code] = region.id
        print(f"  {name}: id={region.id}")
    return mapping


def import_countries(nb, continent_map: dict[str, int], countries: list[dict]) -> dict[str, int]:
    """Create country-level regions under their continent. Returns {iso2: region_id}."""
    print(f"\\n=== Importing {len(countries)} countries as child regions ===")
    country_map = {}
    for c in countries:
        iso = c.get("countryCode", "")
        name = c.get("countryName", "")
        continent_code = c.get("continentName", c.get("continent", ""))

        # Map full continent name back to code if needed
        cont_id = continent_map.get(continent_code)
        if not cont_id:
            for code, cname in CONTINENTS.items():
                if cname == continent_code:
                    cont_id = continent_map.get(code)
                    break
        if not cont_id:
            continue

        slug = _slug(f"{iso}-{name}")
        region = _get_or_create_region(nb, name, slug, parent_id=cont_id)
        country_map[iso] = region.id
    print(f"  Created/verified {len(country_map)} country regions")
    return country_map


def import_cities(nb, country_map: dict[str, int], countries: list[dict]):
    """Create sites for major cities in each country."""
    print(f"\\n=== Importing cities (pop >= {MIN_CITY_POP}) ===")
    total = 0
    for i, c in enumerate(countries):
        iso = c.get("countryCode", "")
        region_id = country_map.get(iso)
        if not region_id:
            continue

        cities = fetch_cities(iso)
        for city in cities:
            name = city.get("name", city.get("toponymName", ""))
            lat = city.get("lat")
            lng = city.get("lng")
            slug = _slug(f"{iso}-{name}")
            try:
                _get_or_create_site(
                    nb, name, slug, region_id,
                    latitude=float(lat) if lat else None,
                    longitude=float(lng) if lng else None,
                )
                total += 1
            except Exception as exc:
                print(f"  WARN: {name} ({iso}): {exc}")

        # Rate limit: brief pause between countries
        if (i + 1) % 10 == 0:
            time.sleep(1)
            print(f"  ... processed {i + 1}/{len(countries)} countries, {total} cities so far")

    print(f"  Total cities imported: {total}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print(f"Connecting to NetBox at {NETBOX_URL}")
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)

    # Verify connectivity
    try:
        status = nb.status()
        print(f"NetBox version: {status.get('netbox-version', 'unknown')}")
    except Exception as exc:
        print(f"ERROR: Cannot reach NetBox API: {exc}", file=sys.stderr)
        sys.exit(1)

    countries = fetch_countries()
    continent_map = import_continents(nb)
    country_map = import_countries(nb, continent_map, countries)
    import_cities(nb, country_map, countries)

    # Summary
    print("\\n=== Import complete ===")
    print(f"  Regions: {nb.dcim.regions.count()}")
    print(f"  Sites:   {nb.dcim.sites.count()}")


if __name__ == "__main__":
    main()
'''


def render_geo_foss_dockerfile(plan: DeploymentPlan) -> str:
    """Render the Dockerfile that builds netbox-geo-foss from its pinned source."""

    return f"""# Auto-generated — builds netbox-geo-foss from source
# Repository: {plan.geo_foss.repository}
# Ref: {plan.geo_foss.ref}
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    PIP_DEFAULT_TIMEOUT=100

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential curl git \\
    libgeos-dev libproj-dev libgdal-dev \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone {plan.geo_foss.repository} . \\
    && git checkout {plan.geo_foss.ref}

RUN python -m venv /app/.venv \\
    && /app/.venv/bin/pip install --upgrade pip setuptools wheel \\
    && /app/.venv/bin/pip install -r requirements/base.txt \\
    && /app/.venv/bin/pip install .

# --- runtime ---
FROM python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser appuser

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PATH="/app/.venv/bin:$PATH" \\
    PYTHONPATH="/app/src:$PYTHONPATH"

RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl libgeos-c1v5 libproj25 gdal-bin libgdal36 \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/cache /app/logs /app/tmp && chown -R appuser:appuser /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /build/src /app/src
COPY --from=builder /build/pyproject.toml /app/

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import netbox_geo; print(netbox_geo.__version__)" || exit 1

CMD ["netbox-geo", "--help"]
"""


def render_device_type_library_import_script(plan: DeploymentPlan) -> str:
    """Render a wrapper script for the pinned importer container."""

    return """#!/bin/sh
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
"""


def render_device_type_library_import_runner() -> str:
    """Render a REST-API-based importer for the community device-type library."""

    return '''#!/usr/bin/env python3
"""Import device-type-library YAML files into NetBox via its REST API.

Creates manufacturers, device types (with component templates),
module types (with component templates), and rack types.
Idempotent: existing objects are skipped.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen, urlretrieve

import yaml

# ── YAML keys that are NOT device-/module-type API fields ──
COMPONENT_KEYS = frozenset({
    "interfaces", "console-ports", "console-server-ports",
    "power-ports", "power-outlets", "front-ports", "rear-ports",
    "device-bays", "module-bays", "inventory-items",
})
DTLI_ONLY_KEYS = frozenset({
    "manufacturer", "is_powered", "front_image", "rear_image",
})

# YAML key → API list endpoint (relative to /api/dcim/)
COMPONENT_ENDPOINTS: dict[str, str] = {
    "interfaces":           "interface-templates",
    "console-ports":        "console-port-templates",
    "console-server-ports": "console-server-port-templates",
    "power-ports":          "power-port-templates",
    "power-outlets":        "power-outlet-templates",
    "rear-ports":           "rear-port-templates",
    "front-ports":          "front-port-templates",
    "device-bays":          "device-bay-templates",
    "module-bays":          "module-bay-templates",
    "inventory-items":      "inventory-item-templates",
}

# Component keys whose items may reference another template by name.
# Maps yaml_key → (field_in_yaml, api_field_name, referenced_yaml_key)
COMPONENT_REFS: dict[str, tuple[str, str, str]] = {
    "power-outlets": ("power_port", "power_port_template", "power-ports"),
    "front-ports":   ("rear_port",  "rear_port_template",  "rear-ports"),
}

# ── helpers ──

def _slugify(value: str) -> str:
    return re.sub(r"\\W+", "-", value.casefold()).strip("-")


def _split_csv(value: str) -> set[str]:
    return {item.strip().casefold() for item in value.split(",") if item.strip()}


# ── lightweight REST client (stdlib only) ──

class NetBoxAPI:
    def __init__(self, base_url: str, bearer_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # -- low level --

    def _request(self, method: str, path: str, body: object = None,
                 params: dict[str, str] | None = None) -> tuple[int, object]:
        url = f"{self._base}{path}"
        if params:
            url += "?" + urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = Request(url, data=data, method=method, headers=self._headers)
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def get(self, path: str, **params: str) -> tuple[int, object]:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: object) -> tuple[int, object]:
        return self._request("POST", path, body)

    # -- convenience --

    def get_or_create(self, path: str, lookup: dict[str, str],
                      create: dict[str, object]) -> tuple[dict, bool]:
        status, data = self.get(path, **lookup)
        if status == 200 and data.get("count", 0) > 0:
            return data["results"][0], False
        status, data = self.post(path, create)
        if status == 201:
            return data, True
        # Race or slug collision: retry by original lookup then by slug
        if status == 400:
            status2, data2 = self.get(path, **lookup)
            if status2 == 200 and data2.get("count", 0) > 0:
                return data2["results"][0], False
            slug = create.get("slug")
            if slug:
                status3, data3 = self.get(path, slug=slug)
                if status3 == 200 and data3.get("count", 0) > 0:
                    return data3["results"][0], False
        raise RuntimeError(f"Failed to create {path}: HTTP {status}: {data}")

    def bulk_create(self, path: str, items: list[dict]) -> list[dict]:
        if not items:
            return []
        status, data = self.post(path, items)
        if status == 201:
            return data if isinstance(data, list) else [data]
        raise RuntimeError(f"Bulk create {path}: HTTP {status}: {data}")


# ── library download ──

def _download_library() -> Path:
    archive_url = os.environ["DEVICE_TYPE_LIBRARY_ARCHIVE_URL"]
    working_dir = Path(tempfile.mkdtemp(prefix="netbox-device-library-"))
    archive_path = working_dir / "library.tar.gz"
    extract_dir = working_dir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    urlretrieve(archive_url, archive_path)
    with tarfile.open(archive_path, mode="r:gz") as archive:
        archive.extractall(extract_dir)

    roots = sorted(p for p in extract_dir.iterdir() if p.is_dir())
    if not roots:
        raise RuntimeError(f"Archive empty: {archive_url}")
    return roots[0]


def _iter_definition_files(root: Path, directory_name: str,
                           vendors: set[str]) -> list[Path]:
    base_dir = root / directory_name
    if not base_dir.exists():
        return []
    files: list[Path] = []
    for vendor_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        if vendors and vendor_dir.name.casefold() not in vendors:
            continue
        for pattern in ("*.yaml", "*.yml"):
            files.extend(sorted(vendor_dir.glob(pattern)))
    return files


def _load_documents(paths: list[Path]) -> list[tuple[Path, dict[str, object]]]:
    docs: list[tuple[Path, dict[str, object]]] = []
    for path in paths:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise RuntimeError(f"Expected YAML object in {path}")
        docs.append((path, doc))
    return docs


# ── import logic ──

def _collect_manufacturers(
    *doc_sets: list[tuple[Path, dict[str, object]]],
) -> dict[str, dict[str, str]]:
    mfgs: dict[str, dict[str, str]] = {}
    for doc_set in doc_sets:
        for _, doc in doc_set:
            name = doc.get("manufacturer")
            if isinstance(name, str) and name not in mfgs:
                mfgs[name] = {"name": name, "slug": _slugify(name)}
    return mfgs


def _import_manufacturers(api: NetBoxAPI,
                          mfgs: dict[str, dict[str, str]]) -> dict[str, int]:
    name_to_id: dict[str, int] = {}
    for name in sorted(mfgs, key=str.casefold):
        obj, created = api.get_or_create(
            "/api/dcim/manufacturers/",
            lookup={"name": name},
            create=mfgs[name],
        )
        name_to_id[name] = obj["id"]
        tag = "created" if created else "exists"
        print(f"  {tag}: {name} (id={obj['id']})")
    return name_to_id


def _import_components(api: NetBoxAPI, parent_key: str, parent_id: int,
                       doc: dict[str, object],
                       mfg_ids: dict[str, int] | None = None) -> None:
    """Import component templates for a device type or module type."""
    # First pass: components that do NOT reference other templates.
    created_name_ids: dict[str, dict[str, int]] = {}
    for yaml_key in (
        "interfaces", "console-ports", "console-server-ports",
        "power-ports", "rear-ports",
        "device-bays", "module-bays", "inventory-items",
    ):
        items = doc.get(yaml_key)
        if not items:
            continue
        endpoint = f"/api/dcim/{COMPONENT_ENDPOINTS[yaml_key]}/"
        api_items = []
        for item in items:
            api_item: dict[str, object] = {parent_key: parent_id, **item}
            # Resolve manufacturer name -> ID for inventory items
            if "manufacturer" in api_item and mfg_ids:
                mfg_val = api_item["manufacturer"]
                if isinstance(mfg_val, str):
                    resolved = mfg_ids.get(mfg_val)
                    if resolved is not None:
                        api_item["manufacturer"] = resolved
                    else:
                        del api_item["manufacturer"]
            api_items.append(api_item)
        try:
            results = api.bulk_create(endpoint, api_items)
        except RuntimeError as exc:
            print(f"    {yaml_key}: ERROR {exc}")
            continue
        created_name_ids[yaml_key] = {r["name"]: r["id"] for r in results}
        print(f"    {yaml_key}: {len(results)}")

    # Second pass: components that reference templates created above.
    for yaml_key, (src_field, api_field, ref_key) in COMPONENT_REFS.items():
        items = doc.get(yaml_key)
        if not items:
            continue
        ref_ids = created_name_ids.get(ref_key, {})
        endpoint = f"/api/dcim/{COMPONENT_ENDPOINTS[yaml_key]}/"
        api_items = []
        for item in items:
            api_item: dict[str, object] = {parent_key: parent_id}
            for k, v in item.items():
                if k == src_field and isinstance(v, str):
                    tid = ref_ids.get(v)
                    if tid is not None:
                        api_item[api_field] = tid
                else:
                    api_item[k] = v
            api_items.append(api_item)
        try:
            results = api.bulk_create(endpoint, api_items)
        except RuntimeError as exc:
            print(f"    {yaml_key}: ERROR {exc}")
            continue
        print(f"    {yaml_key}: {len(results)}")


def _import_device_types(api: NetBoxAPI, documents: list[tuple[Path, dict]],
                         mfg_ids: dict[str, int]) -> None:
    for path, doc in documents:
        mfg_name = doc["manufacturer"]
        model = doc.get("model", path.stem)
        slug = doc.get("slug", _slugify(f"{mfg_name}-{model}"))
        payload: dict[str, object] = {
            "manufacturer": mfg_ids[mfg_name], "model": model, "slug": slug,
        }
        for k, v in doc.items():
            if k not in COMPONENT_KEYS and k not in DTLI_ONLY_KEYS and k not in ("model", "slug"):
                payload[k] = v

        try:
            obj, created = api.get_or_create(
                "/api/dcim/device-types/",
                lookup={"slug": slug},
                create=payload,
            )
        except RuntimeError as exc:
            print(f"  ERROR {path.name}: {exc}")
            continue
        tag = "created" if created else "exists"
        print(f"  {tag}: {model} [{slug}] (id={obj['id']})")
        if created:
            _import_components(api, "device_type", obj["id"], doc, mfg_ids)


def _import_module_types(api: NetBoxAPI, documents: list[tuple[Path, dict]],
                         mfg_ids: dict[str, int]) -> None:
    for path, doc in documents:
        mfg_name = doc["manufacturer"]
        model = doc.get("model", path.stem)
        payload: dict[str, object] = {
            "manufacturer": mfg_ids[mfg_name], "model": model,
        }
        for k, v in doc.items():
            if k not in COMPONENT_KEYS and k not in DTLI_ONLY_KEYS and k != "model":
                payload[k] = v

        try:
            obj, created = api.get_or_create(
                "/api/dcim/module-types/",
                lookup={"manufacturer_id": str(mfg_ids[mfg_name]), "model": model},
                create=payload,
            )
        except RuntimeError as exc:
            print(f"  ERROR {path.name}: {exc}")
            continue
        tag = "created" if created else "exists"
        print(f"  {tag}: {model} (id={obj['id']})")
        if created:
            _import_components(api, "module_type", obj["id"], doc, mfg_ids)


def _import_rack_types(api: NetBoxAPI, documents: list[tuple[Path, dict]],
                       mfg_ids: dict[str, int]) -> None:
    for path, doc in documents:
        mfg_name = doc["manufacturer"]
        model = doc.get("model", path.stem)
        slug = doc.get("slug", _slugify(f"{mfg_name}-{model}"))
        payload: dict[str, object] = {
            "manufacturer": mfg_ids[mfg_name], "model": model, "slug": slug,
        }
        for k, v in doc.items():
            if k not in DTLI_ONLY_KEYS and k not in ("model", "slug"):
                payload[k] = v

        try:
            obj, created = api.get_or_create(
                "/api/dcim/rack-types/",
                lookup={"slug": slug},
                create=payload,
            )
        except RuntimeError as exc:
            print(f"  ERROR {path.name}: {exc}")
            continue
        tag = "created" if created else "exists"
        print(f"  {tag}: {model} [{slug}] (id={obj['id']})")


# ── token construction ──

def _build_bearer_token() -> str:
    """Read the API token plaintext from secrets and look up the DB key."""
    sys.path.insert(0, "/opt/netbox/netbox")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from users.models import Token

    plaintext = Path("/run/secrets/superuser_api_token").read_text("utf-8").strip()
    if not plaintext:
        raise RuntimeError("superuser_api_token secret is empty")

    username_file = os.environ.get("NETBOX_IMPORT_USERNAME_FILE", "/run/secrets/superuser_name")
    username = Path(username_file).read_text("utf-8").strip()

    User = get_user_model()
    user = User.objects.get(username=username)

    for token in Token.objects.filter(user=user):
        if token.validate(plaintext):
            return f"nbt_{token.key}.{plaintext}"

    raise RuntimeError("No matching API token found for the configured user")


# ── main ──

def main() -> None:
    bearer = _build_bearer_token()
    netbox_url = os.environ["NETBOX_URL"].rstrip("/")
    api = NetBoxAPI(netbox_url, bearer)

    status, data = api.get("/api/status/")
    if status != 200:
        raise RuntimeError(f"NetBox API unreachable: HTTP {status}")
    print(f"Connected to NetBox {data.get('netbox-version', '?')}")

    vendors = _split_csv(os.environ.get("DEVICE_TYPE_LIBRARY_VENDORS", ""))
    library_root = _download_library()

    device_docs = _load_documents(_iter_definition_files(library_root, "device-types", vendors))
    module_docs = _load_documents(_iter_definition_files(library_root, "module-types", vendors))
    rack_docs = _load_documents(_iter_definition_files(library_root, "rack-types", vendors))
    print(
        f"Loaded {len(device_docs)} device, {len(module_docs)} module,"
        f" {len(rack_docs)} rack definitions"
    )

    mfgs = _collect_manufacturers(device_docs, module_docs, rack_docs)
    print(f"Importing {len(mfgs)} manufacturers ...")
    mfg_ids = _import_manufacturers(api, mfgs)

    if device_docs:
        print(f"Importing {len(device_docs)} device types ...")
        _import_device_types(api, device_docs, mfg_ids)

    if module_docs:
        print(f"Importing {len(module_docs)} module types ...")
        _import_module_types(api, module_docs, mfg_ids)

    if rack_docs:
        print(f"Importing {len(rack_docs)} rack types ...")
        _import_rack_types(api, rack_docs, mfg_ids)

    print("Import complete.")


if __name__ == "__main__":
    main()
'''


def render_plan_json(plan: DeploymentPlan) -> str:
    """Render the plan as JSON."""

    return json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"


def render_summary_markdown(plan: DeploymentPlan) -> str:
    """Render a human-readable plan summary."""

    plugin_lines = [
        f"- {plugin.module_name} ({plugin.package_name}=={plugin.version}) [{plugin.support_tier}]"
        for plugin in plan.plugins
        if plugin.enabled
    ]
    warning_lines = [f"- {warning}" for warning in plan.warnings] or ["- None"]
    note_lines = [f"- {note}" for note in plan.notes]
    permission_lines = [
        f"- {permission}" for permission in plan.device_type_library.least_privilege_permissions
    ]

    return f"""# Generated Deployment Plan

## Source

- Report: {plan.source_report}
- Generator version: {plan.source_generator_version}
- Deployment name: {plan.deployment_name}

## Host Summary

- Hostname: {plan.host.hostname}
- OS: {plan.host.operating_system} {plan.host.operating_system_version}
- Kernel: {plan.host.kernel_version}
- Architecture: {plan.host.architecture}
- WSL: {plan.host.is_wsl}
- Docker capable: {plan.host.docker_capable}
- Memory total: {plan.host.total_memory_bytes}
- Memory available: {plan.host.available_memory_bytes}

## Standards Alignment

- Deployment pattern follows the official netbox-docker plugin workflow.
- Plugins are configured only through `PLUGINS` and `PLUGINS_CONFIG`.
- Core NetBox behavior is left untouched; integrations are additive.
- User traffic is terminated by Traefik with a generated self-signed TLS certificate.
- A dedicated WAF sidecar (OWASP CRS image) sits between Traefik and NetBox.
- Admin bootstrap is pseudonymous and secret-file backed.
- Least privilege is applied through separated secrets and dropped Linux capabilities;
  the importer can be switched to a dedicated NetBox user when desired.

## Images

- NetBox: {plan.images.netbox_image}
- PostgreSQL: {plan.images.postgres_image}
- Valkey: {plan.images.valkey_image}
- Track: {plan.images.track}
- Lifecycle reference: {plan.images.release_reference}

## Enabled Plugins

{chr(10).join(plugin_lines)}

## Network Plan

- CIDR mode: {plan.networks.cidr_mode}
{_render_network_notes(plan)}

## Container Orchestration

- Worker containers: {max(1, plan.sizing.netbox_worker_containers)}
- Orchestration metadata: `configuration/orb/orchestration.yml`
- ORB sidecar: readiness-gated placeholder that records the generated orchestration file path.

## Device-Type Library

- Library repository: {plan.device_type_library.library_repository}
- Library ref: {plan.device_type_library.library_ref}
- Import service: {plan.device_type_library.import_service_name}
- Rationale: {plan.device_type_library.rationale}

### Least-Privilege Import Permissions

{chr(10).join(permission_lines)}

## Geographic Data (netbox-geo-foss)

- Build: local (Dockerfile-GeoFoss)
- Repository: {plan.geo_foss.repository}
- Ref: {plan.geo_foss.ref}
- Import service: {plan.geo_foss.service_name}
- Rationale: {plan.geo_foss.rationale}

## Privacy Controls

- Bootstrap username: {plan.admin_privacy.bootstrap_username}
- Bootstrap email: {plan.admin_privacy.bootstrap_email}
- Rotation required: {plan.admin_privacy.rotation_required}
- Rationale: {plan.admin_privacy.rationale}

## First Start

- Build the local NetBox plugin image first: `docker compose build`.
- Before running `docker compose up -d`, copy each `secrets/*.example` file to the
  same path without the `.example` suffix.
- Replace the placeholder values in `secrets/db_password`, `secrets/secret_key`,
  `secrets/superuser_password`, `secrets/superuser_api_token`, and
  `secrets/api_token_pepper_1`.
- Keep `secrets/superuser_name` aligned with the pseudonymous bootstrap account unless
  you intentionally rotate it before first start.

## Native Import Workflow

- The generated one-shot import service downloads the pinned device-type library archive.
- Imports run through NetBox core bulk-import views for manufacturers, rack types,
  device types, and module types.
- The default import user is the pseudonymous bootstrap superuser referenced by
  `secrets/superuser_name`.
- For stricter RBAC, create a dedicated NetBox user with the permissions above and
  override `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE`.

## Warnings

{chr(10).join(warning_lines)}

## Notes

{chr(10).join(note_lines)}
"""


def write_bundle(plan: DeploymentPlan, output_dir: Path) -> list[Path]:
    """Write the full deployment bundle."""

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "configuration").mkdir(exist_ok=True)
    (output_dir / "configuration" / "traefik").mkdir(parents=True, exist_ok=True)
    (output_dir / "configuration" / "waf").mkdir(parents=True, exist_ok=True)
    (output_dir / "configuration" / "orb").mkdir(parents=True, exist_ok=True)
    (output_dir / "env").mkdir(exist_ok=True)
    (output_dir / "secrets").mkdir(exist_ok=True)
    (output_dir / "scripts").mkdir(exist_ok=True)

    files: dict[Path, str] = {
        output_dir / "docker-compose.yml": render_compose(plan),
        output_dir / "Dockerfile-Plugins": render_dockerfile_plugins(plan),
        output_dir / "Dockerfile-GeoFoss": render_geo_foss_dockerfile(plan),
        output_dir / "plugin_requirements.txt": render_plugin_requirements(plan),
        output_dir / "configuration" / "plugins.py": render_plugins_py(plan),
        output_dir / "configuration" / "traefik" / "dynamic.yml": render_traefik_dynamic_config(),
        output_dir / "configuration" / "waf" / "default.conf": render_waf_default_conf(),
        output_dir
        / "configuration"
        / "orb"
        / "orchestration.yml": render_orb_orchestration_config(plan),
        output_dir / "env" / "netbox.env": render_netbox_env(plan),
        output_dir / "env" / "postgres.env": render_postgres_env(plan),
        output_dir / "env" / "orb.env": render_orb_env(),
        output_dir
        / "env"
        / "device-type-library-import.env": render_device_type_library_import_env(plan),
        output_dir / "env" / "geo-foss.env": render_geo_foss_env(plan),
        output_dir / "deployment-plan.json": render_plan_json(plan),
        output_dir / "README.md": render_summary_markdown(plan),
        output_dir
        / "scripts"
        / "run-device-type-library-import.sh": render_device_type_library_import_script(
            plan
        ),
        output_dir
        / "scripts"
        / "import-device-type-library.py": render_device_type_library_import_runner(),
        output_dir / "scripts" / "generate-traefik-cert.sh": render_traefik_cert_script(plan),
        output_dir / "scripts" / "sync-superuser.sh": render_superuser_sync_script(),
        output_dir / "scripts" / "run-orb-agent.sh": render_orb_agent_script(),
        output_dir / "scripts" / "run-geo-foss-import.sh": render_geo_foss_import_script(),
        output_dir / "scripts" / "import-geo-data.py": render_geo_foss_import_runner(),
        output_dir / "secrets" / ".gitignore": "*\n!.gitignore\n!*.example\n",
        output_dir / "secrets" / "db_password.example": (
            "replace-with-a-strong-database-password\n"
        ),
        output_dir / "secrets" / "api_token_pepper_1.example": (
          "replace-with-a-64+-character-api-token-pepper-0123456789abcdef0123456789abcdef\n"
        ),
        output_dir / "secrets" / "secret_key.example": (
          "replace-with-a-64+-character-secret-key-0123456789abcdef0123456789abcdef\n"
        ),
        output_dir / "secrets" / "superuser_name.example": (
            f"{plan.admin_privacy.bootstrap_username}\n"
        ),
        output_dir / "secrets" / "superuser_password.example": (
            "replace-with-a-strong-bootstrap-password\n"
        ),
        output_dir / "secrets" / "superuser_api_token.example": (
            "replace-with-a-bootstrap-api-token\n"
        ),
    }

    written: list[Path] = []
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
        if path.suffix in {".sh", ".py"}:
            path.chmod(0o755)
        written.append(path)
    return written
