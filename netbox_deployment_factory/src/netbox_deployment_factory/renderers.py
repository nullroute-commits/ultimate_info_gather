"""Render deployment bundles from a deployment plan."""

from __future__ import annotations

import json
import pprint
import re
from pathlib import Path

from .constants import (
  ALLOY_IMAGE,
  CADVISOR_IMAGE,
  DIODE_AUTH_IMAGE,
  DIODE_INGESTER_IMAGE,
  DIODE_RECONCILER_IMAGE,
  GRAFANA_IMAGE,
  LOKI_IMAGE,
  MONITORING_INIT_IMAGE,
  NODE_EXPORTER_IMAGE,
  OPENSSL_IMAGE,
  ORB_AGENT_IMAGE,
  PROMETHEUS_IMAGE,
  SNMP_EXPORTER_IMAGE,
  SYSLOG_NG_IMAGE,
  TRAEFIK_IMAGE,
  WAF_IMAGE,
  WAZUH_AGENT_IMAGE,
)
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


def render_netbox_extra_py() -> str:
    """Render NetBox settings overrides for reverse-proxy authentication."""

    return '''"""Generated NetBox authentication overrides."""

REMOTE_AUTH_ENABLED = True
REMOTE_AUTH_BACKEND = "netbox.authentication.RemoteUserBackend"
REMOTE_AUTH_HEADER = "HTTP_X_AUTHENTIK_USERNAME"
REMOTE_AUTH_USER_EMAIL = "HTTP_X_AUTHENTIK_EMAIL"
REMOTE_AUTH_AUTO_CREATE_USER = True
'''


def render_dockerfile_plugins(plan: DeploymentPlan) -> str:
    """Render the plugin image Dockerfile."""

    return f"""ARG NETBOX_IMAGE={plan.images.netbox_image}
FROM ${{NETBOX_IMAGE}}

COPY plugin_requirements.txt /opt/netbox/plugin_requirements.txt
RUN /usr/local/bin/uv pip install \
  --python /opt/netbox/venv/bin/python \
  -r /opt/netbox/plugin_requirements.txt

COPY configuration/extra.py /etc/netbox/config/extra.py
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


def _resolve_public_host(plan: DeploymentPlan) -> str:
    if plan.tls.mode == "letsencrypt" and plan.tls.fqdn:
        return plan.tls.fqdn
    if plan.host.service_ip and plan.host.service_ip != "127.0.0.1":
        return plan.host.service_ip
    hostname = plan.host.hostname.strip()
    if hostname and re.fullmatch(
        r"[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*",
        hostname,
    ):
        return hostname
    return "localhost"


def _render_netbox_public_base_url(plan: DeploymentPlan) -> str:
    return f"https://{_resolve_public_host(plan)}"


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
    monitoring_cidr = _segment_cidr(plan, "monitoring")
    identity_cidr = _segment_cidr(plan, "identity")

    use_le = plan.tls.mode == "letsencrypt" and plan.tls.fqdn

    if use_le:
        certgen_block = ""
        traefik_depends = """    depends_on:
      waf:
        condition: service_started"""
        traefik_command = f"""    command:
      - --api.dashboard=false
      - --ping=true
      - --providers.file.directory=/etc/traefik/dynamic
      - --entrypoints.web.address=:80
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --entrypoints.web.http.redirections.entrypoint.scheme=https
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.letsencrypt.acme.email={plan.tls.acme_email}
      - --certificatesresolvers.letsencrypt.acme.storage=/acme/acme.json
      - --certificatesresolvers.letsencrypt.acme.dnschallenge=true
      - --certificatesresolvers.letsencrypt.acme.dnschallenge.provider=cloudflare
      - --certificatesresolvers.letsencrypt.acme.dnschallenge.resolvers=1.1.1.1:53,1.0.0.1:53
      - --log.level=INFO"""
        traefik_ports = f"""    ports:
      - "{plan.host.service_ip}:80:80"
      - "{plan.host.service_ip}:443:443" """
        traefik_volumes = """    volumes:
      - acme-data:/acme
      - ./configuration/traefik:/etc/traefik/dynamic:ro"""
        traefik_env = """    secrets:
      - cf_dns_api_token
    environment:
      - CF_DNS_API_TOKEN_FILE=/run/secrets/cf_dns_api_token"""
    else:
        certgen_block = f"""  traefik-certgen:
    image: {OPENSSL_IMAGE}
    restart: "no"
    entrypoint: ["/bin/sh"]
    command: ["/opt/scripts/generate-traefik-cert.sh"]
    volumes:
      - traefik-certs:/certs
      - ./scripts:/opt/scripts:ro
    networks:
      - edge

"""
        traefik_depends = """    depends_on:
      traefik-certgen:
        condition: service_completed_successfully
      waf:
        condition: service_started"""
        traefik_command = """    command:
      - --api.dashboard=false
      - --ping=true
      - --providers.file.directory=/etc/traefik/dynamic
      - --entrypoints.websecure.address=:443
      - --log.level=INFO"""
        traefik_ports = f"""    ports:
      - "{plan.host.service_ip}:443:443" """
        traefik_volumes = """    volumes:
      - traefik-certs:/certs:ro
      - ./configuration/traefik:/etc/traefik/dynamic:ro"""
        traefik_env = ""

    return f"""services:
{certgen_block}  traefik:
    image: {TRAEFIK_IMAGE}
    restart: unless-stopped
{traefik_depends}
{traefik_command}
{traefik_ports}
{traefik_volumes}
{traefik_env}
    healthcheck:
      test: ["CMD", "wget", "--spider", "--quiet", "http://127.0.0.1:8080/ping"]
      interval: 15s
      timeout: 5s
      retries: 10
    networks:
      - edge
      - app
      - identity

  waf:
    image: {WAF_IMAGE}
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

  diode-auth:
    image: {DIODE_AUTH_IMAGE}
    restart: unless-stopped
    depends_on:
      hydra:
        condition: service_healthy
    env_file:
      - env/diode.env
    ports:
      - "127.0.0.1:18080:8080"
    networks:
      - data
      - identity

  diode-ingester:
    image: {DIODE_INGESTER_IMAGE}
    restart: unless-stopped
    depends_on:
      valkey:
        condition: service_healthy
    env_file:
      - env/diode.env
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - data

  diode-reconciler:
    image: {DIODE_RECONCILER_IMAGE}
    restart: unless-stopped
    depends_on:
      netbox:
        condition: service_healthy
      diode-auth:
        condition: service_started
      valkey:
        condition: service_healthy
      postgres:
        condition: service_healthy
    env_file:
      - env/diode.env
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
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
      diode-auth:
        condition: service_started
    env_file:
      - env/netbox.env
    secrets:
      - db_password
      - api_token_pepper_1
      - secret_key
      - netbox_to_diode
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
      - netbox_to_diode
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

  diode-credential-setup:
    image: {plan.deployment_name}:local
    restart: "no"
    depends_on:
      netbox:
        condition: service_healthy
      netbox-superuser-sync:
        condition: service_completed_successfully
    env_file:
      - env/netbox.env
    secrets:
      - db_password
      - api_token_pepper_1
      - secret_key
      - netbox_to_diode
    command: ["/bin/sh", "/opt/netbox/bootstrap/setup-diode-credential.sh"]
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    tmpfs:
      - /tmp
    volumes:
      - ./scripts:/opt/netbox/bootstrap:ro
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
      - netbox_to_diode
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
    image: {WAZUH_AGENT_IMAGE}
    profiles: ["security-observability"]
    restart: unless-stopped
    network_mode: host
    environment:
      WAZUH_MANAGER: "wazuh-manager"
      WAZUH_AGENT_NAME: "{plan.deployment_name}-wazuh-agent"

  orb-agent:
    image: {ORB_AGENT_IMAGE}
    profiles: ["orb-discovery"]
    restart: unless-stopped
    depends_on:
      diode-auth:
        condition: service_started
    env_file:
      - env/orb.env
    command: ["run", "-c", "/opt/orb/agent.yaml"]
    user: "0:0"
    network_mode: host
    cap_add:
      - NET_ADMIN
      - NET_RAW
    volumes:
      - ./configuration/orb:/opt/orb:ro

  monitoring-dashboard-init:
    image: {MONITORING_INIT_IMAGE}
    profiles: ["monitoring"]
    restart: "no"
    entrypoint: ["/bin/sh"]
    command: ["/opt/scripts/fetch-monitoring-dashboards.sh", "/dashboards/performance_overview"]
    volumes:
      - grafana-dashboards:/dashboards
      - ./scripts:/opt/scripts:ro
    networks:
      - monitoring

  grafana:
    image: {GRAFANA_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    depends_on:
      monitoring-dashboard-init:
        condition: service_completed_successfully
    env_file:
      - env/monitoring.env
    ports:
      - "{plan.host.service_ip}:3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - grafana-dashboards:/var/lib/grafana/dashboards:ro
      - ./configuration/monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    networks:
      - monitoring

  prometheus:
    image: {PROMETHEUS_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    extra_hosts:
      - "node-exporter:host-gateway"
      - "snmp-exporter:host-gateway"
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --web.enable-admin-api
      - --web.enable-lifecycle
    volumes:
      - prometheus-data:/prometheus
      - ./configuration/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    networks:
      - monitoring
      - data

  loki:
    image: {LOKI_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    command: -config.file=/etc/loki/loki-config.yml
    volumes:
      - ./configuration/monitoring/loki/loki-config.yml:/etc/loki/loki-config.yml:ro
    networks:
      - monitoring

  alloy:
    image: {ALLOY_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    command:
      - run
      - /etc/alloy/config.alloy
      - --server.http.listen-addr=0.0.0.0:12345
    ports:
      - "{plan.host.service_ip}:1514:1514"
      - "127.0.0.1:1514:1514"
    volumes:
      - ./configuration/monitoring/alloy/config.alloy:/etc/alloy/config.alloy:ro
    networks:
      - monitoring

  syslog-ng:
    image: {SYSLOG_NG_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    command: -edv
    depends_on:
      alloy:
        condition: service_started
    network_mode: host
    volumes:
      - ./configuration/monitoring/syslog-ng/syslog-ng.conf:/etc/syslog-ng/syslog-ng.conf:ro

  node-exporter:
    image: {NODE_EXPORTER_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    pid: host
    network_mode: host
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro

  snmp-exporter:
    image: {SNMP_EXPORTER_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    network_mode: host

  cadvisor:
    image: {CADVISOR_IMAGE}
    profiles: ["monitoring"]
    restart: unless-stopped
    privileged: true
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:rw
      - /var/run/docker.sock:/var/run/docker.sock:rw
      - /sys:/sys:ro
      - /var/lib/docker:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    devices:
      - /dev/kmsg:/dev/kmsg
    networks:
      - monitoring

  # ═══════════════════════════════════════════════════════════════════════
  # Identity Provider: Authentik
  # ═══════════════════════════════════════════════════════════════════════

  authentik-postgres:
    image: {plan.images.postgres_image}
    profiles: ["identity"]
    restart: unless-stopped
    environment:
      POSTGRES_DB: authentik
      POSTGRES_USER: authentik
      POSTGRES_PASSWORD_FILE: /run/secrets/authentik_pg_password
    secrets:
      - authentik_pg_password
    volumes:
      - authentik-pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d $$POSTGRES_DB -U $$POSTGRES_USER"]
      interval: 15s
      timeout: 5s
      retries: 10
    cap_drop: ["ALL"]
    cap_add: ["DAC_OVERRIDE", "CHOWN", "FOWNER", "SETUID", "SETGID"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - identity

  authentik-server:
    image: {plan.identity.authentik_image}
    profiles: ["identity"]
    command: server
    restart: unless-stopped
    depends_on:
      authentik-postgres:
        condition: service_healthy
    env_file:
      - env/authentik.env
    secrets:
      - authentik_secret_key
      - authentik_pg_password
    shm_size: 512mb
    volumes:
      - authentik-data:/data
    healthcheck:
      test: ["CMD", "ak", "healthcheck"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 60s
    cap_drop: ["ALL"]
    cap_add: ["NET_BIND_SERVICE"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - identity
      - app

  authentik-worker:
    image: {plan.identity.authentik_image}
    profiles: ["identity"]
    command: worker
    restart: unless-stopped
    depends_on:
      authentik-postgres:
        condition: service_healthy
    env_file:
      - env/authentik.env
    secrets:
      - authentik_secret_key
      - authentik_pg_password
    shm_size: 512mb
    volumes:
      - authentik-data:/data
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - identity

  authentik-bootstrap-netbox:
    image: {plan.identity.authentik_image}
    profiles: ["identity"]
    restart: "no"
    depends_on:
      authentik-server:
        condition: service_healthy
      netbox:
        condition: service_healthy
    env_file:
      - env/authentik.env
    environment:
      NETBOX_PUBLIC_URL: {_render_netbox_public_base_url(plan)}
      NETBOX_INTERNAL_URL: http://waf:8081
    secrets:
      - authentik_secret_key
      - authentik_pg_password
    entrypoint: ["/bin/sh", "/opt/authentik/bootstrap/authentik-bootstrap-netbox.sh"]
    volumes:
      - ./scripts:/opt/authentik/bootstrap:ro
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - identity
      - app

  # ═══════════════════════════════════════════════════════════════════════
  # Ory Hydra: OAuth2/OIDC provider for Diode
  # ═══════════════════════════════════════════════════════════════════════

  hydra-postgres:
    image: {plan.images.postgres_image}
    restart: unless-stopped
    environment:
      POSTGRES_DB: hydra
      POSTGRES_USER: hydra
      POSTGRES_PASSWORD_FILE: /run/secrets/hydra_pg_password
    secrets:
      - hydra_pg_password
    volumes:
      - hydra-pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -d $$POSTGRES_DB -U $$POSTGRES_USER"]
      interval: 15s
      timeout: 5s
      retries: 10
    cap_drop: ["ALL"]
    cap_add: ["DAC_OVERRIDE", "CHOWN", "FOWNER", "SETUID", "SETGID"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - identity

  hydra-migrate:
    image: {plan.identity.hydra_image}
    restart: "no"
    depends_on:
      hydra-postgres:
        condition: service_healthy
    env_file:
      - env/hydra.env
    secrets:
      - hydra_pg_password
      - hydra_system_secret
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        hydra_pw="$$(cat /run/secrets/hydra_pg_password)"
        export DSN="postgres://hydra:$$hydra_pw@hydra-postgres:5432/hydra?sslmode=disable"
        export SECRETS_SYSTEM="$$(cat /run/secrets/hydra_system_secret)"
        exec hydra migrate sql --yes --read-from-env
    networks:
      - identity

  hydra:
    image: {plan.identity.hydra_image}
    restart: unless-stopped
    depends_on:
      hydra-migrate:
        condition: service_completed_successfully
    env_file:
      - env/hydra.env
    secrets:
      - hydra_pg_password
      - hydra_system_secret
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        hydra_pw="$$(cat /run/secrets/hydra_pg_password)"
        export DSN="postgres://hydra:$$hydra_pw@hydra-postgres:5432/hydra?sslmode=disable"
        export SECRETS_SYSTEM="$$(cat /run/secrets/hydra_system_secret)"
        exec hydra serve all --dev
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:4444/health/alive || exit 1"]
      interval: 15s
      timeout: 5s
      retries: 10
    cap_drop: ["ALL"]
    security_opt: ["no-new-privileges:true"]
    networks:
      - identity
      - data

  hydra-bootstrap-clients:
    image: {plan.identity.hydra_image}
    restart: "no"
    depends_on:
      hydra:
        condition: service_healthy
    env_file:
      - env/hydra.env
    secrets:
      - hydra_pg_password
      - hydra_system_secret
      - diode_client_id
      - diode_client_secret
    entrypoint: ["/bin/sh", "-c"]
    command:
      - |
        DIODE_CLIENT_ID=$$(cat /run/secrets/diode_client_id)
        DIODE_CLIENT_SECRET=$$(cat /run/secrets/diode_client_secret)
        hydra delete oauth2-client "$$DIODE_CLIENT_ID" \
          --endpoint http://hydra:4445 2>/dev/null || true
        hydra create oauth2-client \
          --endpoint http://hydra:4445 \
          --id "$$DIODE_CLIENT_ID" \
          --secret "$$DIODE_CLIENT_SECRET" \
          --grant-type client_credentials \
          --scope openid,diode \
          --token-endpoint-auth-method client_secret_post
        echo "Diode OAuth2 client registered successfully"
        NETBOX_CLIENT_ID="netbox-to-diode"
        hydra delete oauth2-client "$$NETBOX_CLIENT_ID" \
          --endpoint http://hydra:4445 2>/dev/null || true
        hydra create oauth2-client \
          --endpoint http://hydra:4445 \
          --id "$$NETBOX_CLIENT_ID" \
          --secret "$$DIODE_CLIENT_SECRET" \
          --grant-type client_credentials \
          --scope openid,diode \
          --token-endpoint-auth-method client_secret_post
        echo "NetBox-to-Diode OAuth2 client registered successfully"
    networks:
      - identity

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
  diode_redis_password:
    file: secrets/diode_redis_password
  netbox_to_diode:
    file: secrets/netbox_to_diode
  diode_client_id:
    file: secrets/diode_client_id
  diode_client_secret:
    file: secrets/diode_client_secret
  authentik_secret_key:
    file: secrets/authentik_secret_key
  authentik_pg_password:
    file: secrets/authentik_pg_password
  hydra_pg_password:
    file: secrets/hydra_pg_password
  hydra_system_secret:
    file: secrets/hydra_system_secret
{"  cf_dns_api_token:" + chr(10) + "    file: secrets/cf_dns_api_token" if use_le else ""}

volumes:
{"  acme-data:" if use_le else "  traefik-certs:"}
  postgres-data:
  valkey-data:
  netbox-media:
  netbox-reports:
  netbox-scripts:
  geo-foss-cache:
  token-store:
  grafana-data:
  grafana-dashboards:
  prometheus-data:
  authentik-pg-data:
  authentik-data:
  hydra-pg-data:

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
  monitoring:
    driver: bridge
    ipam:
      config:
        - subnet: {monitoring_cidr}
  identity:
    driver: bridge
    ipam:
      config:
        - subnet: {identity_cidr}
"""


def render_netbox_env(plan: DeploymentPlan) -> str:
    """Render the NetBox application environment."""

    allowed_hosts = f"localhost 127.0.0.1 netbox traefik waf {plan.host.hostname}"
    csrf_origins = f"https://localhost https://{plan.host.hostname}"
    if plan.host.service_ip and plan.host.service_ip != "127.0.0.1":
        allowed_hosts = f"{allowed_hosts} {plan.host.service_ip}"
        csrf_origins = f"{csrf_origins} https://{plan.host.service_ip}"
    if plan.tls.mode == "letsencrypt" and plan.tls.fqdn:
        allowed_hosts = f"{allowed_hosts} {plan.tls.fqdn}"
        csrf_origins = f"{csrf_origins} https://{plan.tls.fqdn}"

    return f"""ALLOWED_HOSTS={allowed_hosts}
CSRF_TRUSTED_ORIGINS={csrf_origins}
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


def render_traefik_dynamic_config(plan: DeploymentPlan) -> str:
    """Render the base Traefik dynamic config (works without identity profile).

    This config routes all HTTPS traffic to NetBox via the WAF sidecar.
    Authentik SSO routers and forwardAuth middleware are in a separate
    ``dynamic-identity.yml`` that should only be active when the identity
    Compose profile is enabled.
    """

    if plan.tls.mode == "letsencrypt" and plan.tls.fqdn:
        fqdn = plan.tls.fqdn
        tls_block = ""
        router_tls = f"""tls:
        certResolver: letsencrypt
        domains:
          - main: "{fqdn}" """
    else:
        tls_block = """tls:
  certificates:
    - certFile: /certs/tls.crt
      keyFile: /certs/tls.key

"""
        router_tls = "tls: {}"

    return f"""{tls_block}http:
  routers:
    netbox:
      rule: "PathPrefix(`/`)"
      entryPoints:
        - websecure
      {router_tls}
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
      compress: {{}}
"""


def render_traefik_identity_config(plan: DeploymentPlan) -> str:
    """Render the identity-profile Traefik overlay.

    This file is placed in the Traefik dynamic config directory as
    ``dynamic-identity.yml.disabled``.  Rename it to
    ``dynamic-identity.yml`` when enabling the ``identity`` Compose
    profile so that Authentik SSO protects the NetBox UI.

    It adds:
    - ``netbox-sso`` router (priority 1) that applies ``authentik-forward-auth``
      in front of the WAF, shadowing the base ``netbox`` router.
    - ``authentik-core`` and ``authentik-outpost`` routers for Authentik UI.
    - Authentik load-balancer services and middleware definitions.
    """

    if plan.tls.mode == "letsencrypt" and plan.tls.fqdn:
        fqdn = plan.tls.fqdn
        router_tls = f"""tls:
        certResolver: letsencrypt
        domains:
          - main: "{fqdn}" """
    else:
        router_tls = "tls: {}"

    return f"""# Identity-profile Traefik overlay.
# Rename this file from dynamic-identity.yml.disabled to
# dynamic-identity.yml when enabling the 'identity' Compose profile.
http:
  routers:
    netbox-sso:
      rule: "PathPrefix(`/`)"
      entryPoints:
        - websecure
      {router_tls}
      service: netbox-waf
      middlewares:
        - authentik-forward-auth
        - netbox-compress
      priority: 1

    authentik-core:
      rule: >-
        PathPrefix(`/application/`) || PathPrefix(`/if/`) ||
        PathPrefix(`/static/dist/`)
      entryPoints:
        - websecure
      {router_tls}
      service: authentik-core
      middlewares:
        - authentik-headers
        - netbox-compress
      priority: 110

    authentik-outpost:
      rule: "PathPrefix(`/outpost.goauthentik.io/`)"
      entryPoints:
        - websecure
      {router_tls}
      service: authentik-outpost
      middlewares:
        - authentik-headers
        - netbox-compress
      priority: 100

  services:
    authentik-core:
      loadBalancer:
        servers:
          - url: "http://authentik-server:9000"

    authentik-outpost:
      loadBalancer:
        servers:
          - url: "http://authentik-server:9000/outpost.goauthentik.io"

  middlewares:
    authentik-forward-auth:
      forwardAuth:
        address: "http://authentik-server:9000/outpost.goauthentik.io/auth/traefik"
        trustForwardHeader: true
        authResponseHeaders:
          - X-authentik-username
          - X-authentik-email
          - X-authentik-name
          - X-authentik-groups

    authentik-headers:
      headers:
        customRequestHeaders:
          X-Forwarded-Proto: "https"
"""


def render_waf_default_conf() -> str:
    """Render the WAF sidecar reverse proxy config."""

    return """server {
    listen 8081;
    server_name _;
    resolver 127.0.0.11 valid=30s ipv6=off;

    location / {
        set $netbox_upstream http://netbox:8080;
        proxy_pass $netbox_upstream;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port 443;
        proxy_set_header X-authentik-username $http_x_authentik_username;
        proxy_set_header X-authentik-email $http_x_authentik_email;
        proxy_set_header X-authentik-name $http_x_authentik_name;
        proxy_set_header X-authentik-groups $http_x_authentik_groups;
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
    service_ip = plan.host.service_ip
    if service_ip and service_ip != "127.0.0.1":
        ip_entry = f"IP:{service_ip}"
        if ip_entry not in san_entries:
            san_entries.append(ip_entry)
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


def render_authentik_netbox_bootstrap_script() -> str:
  """Render a one-shot script that provisions Authentik for NetBox forward auth."""

  return '''#!/bin/sh
set -eu

/ak-root/.venv/bin/python -u -m manage shell <<'PY'
import os

from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.core.models import PropertyMapping
from authentik.outposts.models import Outpost
from authentik.providers.oauth2.models import RedirectURI, RedirectURIMatchingMode
from authentik.providers.proxy.models import ProxyMode, ProxyProvider

public_url = os.environ["NETBOX_PUBLIC_URL"].rstrip("/")
internal_url = os.environ.get("NETBOX_INTERNAL_URL", "http://waf:8081").rstrip("/")
callback_url = (
  f"{public_url}/outpost.goauthentik.io/callback"
  "?X-authentik-auth-callback=true"
)

auth_flow = Flow.objects.get(slug="default-authentication-flow")
authorization_flow = Flow.objects.get(
  slug="default-provider-authorization-implicit-consent"
)

provider, created = ProxyProvider.objects.update_or_create(
  name="NetBox Proxy Provider",
  defaults={
    "authentication_flow": auth_flow,
    "authorization_flow": authorization_flow,
    "external_host": public_url,
    "internal_host": internal_url,
    "mode": ProxyMode.FORWARD_SINGLE,
  },
)
provider.redirect_uris = [
  RedirectURI(
    matching_mode=RedirectURIMatchingMode.STRICT,
    url=callback_url,
  )
]
provider.property_mappings.set([
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: OpenID 'openid'"),
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: OpenID 'profile'"),
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: OpenID 'email'"),
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: Proxy outpost"),
])
provider.save()

application, _ = Application.objects.update_or_create(
  slug="netbox",
  defaults={
    "name": "NetBox",
    "provider": provider,
    "meta_launch_url": public_url,
  },
)

embedded_outpost = Outpost.objects.get(name="authentik Embedded Outpost")
embedded_outpost_config = embedded_outpost.config
embedded_outpost_config.authentik_host = public_url
embedded_outpost_config.authentik_host_browser = public_url
embedded_outpost.config = embedded_outpost_config
embedded_outpost.save()
embedded_outpost.providers.add(provider)

print(
  "authentik-bootstrap-netbox:",
  f"provider={'created' if created else 'updated'}",
  f"application={application.slug}",
  f"public_url={public_url}",
  f"internal_url={internal_url}",
  f"callback_url={callback_url}",
)
PY
'''


def render_orb_agent_config() -> str:
    """Render an ORB agent.yaml aligned to upstream orb-agent docs."""

    return """orb:
  config_manager:
    active: local
  secrets_manager:
    active: none
  backends:
    network_discovery:
      nmap:
        args:
          - "-sS"
          - "-sV"
          - "-O"
          - "-A"
          - "--script=default,vuln"
          - "-T4"
          - "--min-rate=300"
          - "--max-retries=3"
        timeout: 30m
    common:
      diode:
        target: grpc://127.0.0.1:18080
        client_id: netbox-to-diode
        client_secret: replace-me
        agent_name: generated-orb-agent
        dry_run: true
  policies:
    network_discovery:
      default:
        config:
          schedule: "@every 120m"
          timeout: 30m
        scope:
          targets:
            - 10.0.0.0/8
            - 172.16.0.0/12
            - 192.168.0.0/16
"""


def render_authentik_env() -> str:
    """Render the Authentik identity provider environment."""

    return """\
# Authentik Identity Provider
AUTHENTIK_POSTGRESQL__HOST=authentik-postgres
AUTHENTIK_POSTGRESQL__PORT=5432
AUTHENTIK_POSTGRESQL__NAME=authentik
AUTHENTIK_POSTGRESQL__USER=authentik
AUTHENTIK_POSTGRESQL__PASSWORD=file:///run/secrets/authentik_pg_password
AUTHENTIK_SECRET_KEY=file:///run/secrets/authentik_secret_key
AUTHENTIK_ERROR_REPORTING__ENABLED=false
AUTHENTIK_LOG_LEVEL=info
AUTHENTIK_LISTEN__HTTP=0.0.0.0:9000
AUTHENTIK_LISTEN__HTTPS=0.0.0.0:9443
"""


def render_hydra_env() -> str:
    """Render the Ory Hydra OAuth2 server environment."""

    return """\
# Ory Hydra OAuth2 Server
LOG_LEVEL=info
URLS_SELF_ISSUER=http://hydra:4444
URLS_SELF_PUBLIC=http://hydra:4444
SERVE_PUBLIC_PORT=4444
SERVE_ADMIN_PORT=4445
DSN=postgres://hydra:replace-me@hydra-postgres:5432/hydra?sslmode=disable
SECRETS_SYSTEM=replace-me
OIDC_SUBJECT_IDENTIFIERS_SUPPORTED_TYPES=public
"""


def render_orb_env() -> str:
    """Render ORB sidecar environment values."""

    return """DIODE_TARGET=grpc://127.0.0.1:18080
ORB_AGENT_CONFIG=/opt/orb/agent.yaml
"""


def render_diode_env() -> str:
    """Render shared Diode service environment defaults."""

    return """ENVIRONMENT=development
LOGGING_LEVEL=info
LOGGING_FORMAT=text
SERVICE_NAME=diode
REDIS_HOST=valkey
REDIS_PORT=6379
REDIS_TLS=false
REDIS_PASSWORD=replace-me
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB_NAME=netbox
POSTGRES_USER=netbox
POSTGRES_PASSWORD=replace-me
POSTGRES_SSL_MODE=disable
DIODE_AUTH_TOKEN_URL=http://diode-auth:8080/token
DIODE_TO_NETBOX_CLIENT_ID=netbox-to-diode
DIODE_TO_NETBOX_CLIENT_SECRET=replace-me
NETBOX_DIODE_PLUGIN_API_BASE_URL=http://netbox:8080/api/plugins/netbox_diode_plugin
NETBOX_DIODE_PLUGIN_SKIP_TLS_VERIFY=true
# Ory Hydra OAuth2 endpoints (consumed by diode-auth)
OAUTH2_PUBLIC_SERVER_URL=http://hydra:4444
OAUTH2_ADMIN_SERVER_URL=http://hydra:4445
"""


def render_diode_ingester_script() -> str:
    """Render a Diode ingester entrypoint that loads secrets into env vars."""

    return """#!/bin/sh
set -eu

export REDIS_PASSWORD="$(cat /run/secrets/diode_redis_password)"
exec /usr/local/bin/diode-server
"""


def render_diode_reconciler_script() -> str:
    """Render a Diode reconciler entrypoint that loads required secrets."""

    return """#!/bin/sh
set -eu

export REDIS_PASSWORD="$(cat /run/secrets/diode_redis_password)"
export POSTGRES_PASSWORD="$(cat /run/secrets/db_password)"
export DIODE_TO_NETBOX_CLIENT_ID="netbox-to-diode"
export DIODE_TO_NETBOX_CLIENT_SECRET="$(cat /run/secrets/netbox_to_diode)"
exec /usr/local/bin/diode-server
"""


def render_diode_credential_setup_script() -> str:
    """Render a one-shot script that creates a diode admin user and API token."""

    return """#!/bin/sh
set -eu

DIODE_CLIENT_SECRET=""
if [ -f /run/secrets/netbox_to_diode ]; then
  DIODE_CLIENT_SECRET="$(cat /run/secrets/netbox_to_diode)"
fi

export DIODE_CLIENT_SECRET
/opt/netbox/venv/bin/python -u /opt/netbox/netbox/manage.py shell <<'PY'
from django.contrib.auth import get_user_model
import os

username = "diode"
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
if changed:
  user.save()

print(f"diode-setup: user='{username}' created={created} changed={changed}")

# Ensure an API token exists for the diode user
from users.models import Token
tokens = Token.objects.filter(user=user)
if not tokens.exists():
  token = Token.objects.create(user=user)
  print(f"diode-setup: created API token key={token.key}")
else:
  print(f"diode-setup: API token already exists for '{username}'")
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

    return """NETBOX_URL=http://netbox:8080
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
import urllib.parse
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

GEONAMES_API = "https://secure.geonames.org"

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
    qs = urllib.parse.urlencode(params)
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


# Major cities per country (fallback when GeoNames is unavailable).
# Values are plain city name lists; fetch_cities() wraps them as dicts.
FALLBACK_CITIES: dict[str, list[str]] = {
    "US": [
        "New York", "Los Angeles", "Chicago", "Houston",
        "Phoenix", "San Francisco", "Seattle", "Dallas",
        "Miami", "Atlanta", "Denver", "Boston", "Washington",
    ],
    "GB": [
        "London", "Manchester", "Birmingham",
        "Edinburgh", "Glasgow", "Bristol", "Leeds",
    ],
    "DE": [
        "Berlin", "Munich", "Frankfurt", "Hamburg",
        "Cologne", "Stuttgart", "Dusseldorf",
    ],
    "FR": [
        "Paris", "Marseille", "Lyon",
        "Toulouse", "Nice", "Strasbourg",
    ],
    "JP": [
        "Tokyo", "Osaka", "Yokohama",
        "Nagoya", "Fukuoka", "Sapporo",
    ],
    "CN": [
        "Shanghai", "Beijing", "Shenzhen", "Guangzhou",
        "Chengdu", "Hangzhou", "Wuhan",
    ],
    "IN": [
        "Mumbai", "Delhi", "Bangalore", "Hyderabad",
        "Chennai", "Kolkata", "Pune",
    ],
    "BR": [
        "Sao Paulo", "Rio de Janeiro", "Brasilia",
        "Salvador", "Fortaleza", "Belo Horizonte",
    ],
    "AU": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
    "CA": [
        "Toronto", "Montreal", "Vancouver",
        "Calgary", "Ottawa", "Edmonton",
    ],
    "KR": ["Seoul", "Busan", "Incheon", "Daegu"],
    "MX": [
        "Mexico City", "Guadalajara", "Monterrey",
        "Puebla", "Tijuana",
    ],
    "IT": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "ES": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"],
    "NL": ["Amsterdam", "Rotterdam", "The Hague", "Utrecht"],
    "SE": ["Stockholm", "Gothenburg", "Malmo"],
    "CH": ["Zurich", "Geneva", "Basel", "Bern"],
    "SG": ["Singapore"],
    "IE": ["Dublin", "Cork"],
    "IL": ["Tel Aviv", "Jerusalem", "Haifa"],
    "AE": ["Dubai", "Abu Dhabi"],
    "ZA": ["Johannesburg", "Cape Town", "Durban", "Pretoria"],
    "NG": ["Lagos", "Abuja", "Kano"],
    "EG": ["Cairo", "Alexandria", "Giza"],
    "KE": ["Nairobi", "Mombasa"],
    "PL": ["Warsaw", "Krakow", "Wroclaw", "Gdansk"],
    "RU": ["Moscow", "Saint Petersburg", "Novosibirsk"],
    "TR": ["Istanbul", "Ankara", "Izmir"],
    "SA": ["Riyadh", "Jeddah", "Mecca"],
    "ID": ["Jakarta", "Surabaya", "Bandung"],
    "TH": ["Bangkok", "Chiang Mai"],
    "VN": ["Ho Chi Minh City", "Hanoi"],
    "PH": ["Manila", "Quezon City", "Cebu City"],
    "MY": ["Kuala Lumpur", "Penang"],
    "PK": ["Karachi", "Lahore", "Islamabad"],
    "BD": ["Dhaka", "Chittagong"],
    "AR": ["Buenos Aires", "Cordoba", "Rosario"],
    "CL": ["Santiago", "Valparaiso"],
    "CO": ["Bogota", "Medellin", "Cali"],
    "PE": ["Lima", "Arequipa"],
    "AT": ["Vienna", "Graz", "Salzburg"],
    "BE": ["Brussels", "Antwerp", "Ghent"],
    "DK": ["Copenhagen", "Aarhus"],
    "FI": ["Helsinki", "Espoo", "Tampere"],
    "NO": ["Oslo", "Bergen"],
    "PT": ["Lisbon", "Porto"],
    "GR": ["Athens", "Thessaloniki"],
    "CZ": ["Prague", "Brno"],
    "RO": ["Bucharest", "Cluj-Napoca"],
    "HU": ["Budapest", "Debrecen"],
    "BG": ["Sofia", "Plovdiv"],
    "HR": ["Zagreb", "Split"],
    "UA": ["Kyiv", "Kharkiv", "Odesa", "Lviv"],
    "NZ": ["Auckland", "Wellington", "Christchurch"],
    "HK": ["Hong Kong"],
    "TW": ["Taipei", "Kaohsiung", "Taichung"],
    "IR": ["Tehran", "Isfahan", "Mashhad"],
    "IQ": ["Baghdad", "Basra", "Erbil"],
    "GH": ["Accra", "Kumasi"],
    "MA": ["Casablanca", "Rabat", "Marrakech"],
    "ET": ["Addis Ababa", "Dire Dawa"],
    "DZ": ["Algiers", "Oran"],
    "AF": ["Kabul", "Kandahar"],
}


def fetch_cities(country_code: str, max_rows: int = 50) -> list[dict]:
    """Fetch major cities for a country from GeoNames (cached), with fallback."""
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
    if not cities:
        fallback = FALLBACK_CITIES.get(country_code, [])
        cities = [{"name": c} for c in fallback]
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
    """Create city-level regions under each country region."""
    print(f"\\n=== Importing cities as regions (pop >= {MIN_CITY_POP}) ===")
    total = 0
    for i, c in enumerate(countries):
        iso = c.get("countryCode", "")
        region_id = country_map.get(iso)
        if not region_id:
            continue

        cities = fetch_cities(iso)
        for city in cities:
            name = city.get("name", city.get("toponymName", ""))
            slug = _slug(f"{iso}-{name}")
            try:
                _get_or_create_region(nb, name, slug, parent_id=region_id)
                total += 1
            except Exception as exc:
                print(f"  WARN: {name} ({iso}): {exc}")

        # Rate limit: brief pause between countries
        if (i + 1) % 10 == 0:
            time.sleep(1)
            print(f"  ... processed {i + 1}/{len(countries)} countries, {total} cities so far")

    print(f"  Total city regions imported: {total}")


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
        for member in archive.getmembers():
            if member.name.startswith("/") or ".." in member.name.split("/"):
                raise RuntimeError(f"Unsafe archive member: {member.name}")
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


def render_prometheus_config() -> str:
    """Render the Prometheus configuration."""

    return """global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    origin_prometheus: netbox-stack

alerting:
  alertmanagers:
  - static_configs:
    - targets: []

rule_files: []

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
    - targets: ['prometheus:9090']

  - job_name: 'grafana'
    static_configs:
    - targets: ['grafana:3000']

  - job_name: 'loki'
    static_configs:
    - targets: ['loki:3100']

  - job_name: 'alloy'
    static_configs:
    - targets: ['alloy:12345']

  - job_name: 'node-exporter'
    static_configs:
    - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
    - targets: ['cadvisor:8080']

  - job_name: 'netbox'
    metrics_path: /metrics
    static_configs:
    - targets: ['netbox:8080']

  - job_name: 'snmp-exporter'
    static_configs:
    - targets: ['snmp-exporter:9116']
"""


def render_loki_config() -> str:
    """Render the Loki configuration."""

    return """auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  path_prefix: /tmp/loki
  storage:
    filesystem:
      chunks_directory: /tmp/loki/chunks
      rules_directory: /tmp/loki/rules
  replication_factor: 1
  ring:
    instance_addr: 127.0.0.1
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

query_scheduler:
  max_outstanding_requests_per_tenant: 10000

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  max_query_series: 5000

ruler:
  alertmanager_url: http://localhost:9093

analytics:
  reporting_enabled: false
"""


def render_alloy_config() -> str:
    """Render the Grafana Alloy configuration."""

    return r"""// Syslog receiver - listens for syslog messages forwarded from syslog-ng
loki.source.syslog "syslog" {
  listener {
    address               = "0.0.0.0:1514"
    protocol              = "tcp"
    idle_timeout          = "60s"
    label_structured_data = true
    labels                = {
      job = "syslog",
    }
  }

  forward_to = [loki.relabel.syslog.receiver]
}

// Relabel syslog messages to extract hostname
loki.relabel "syslog" {
  rule {
    source_labels = ["__syslog_message_hostname"]
    target_label  = "host"
  }

  forward_to = [loki.process.syslog.receiver]
}

// Process syslog messages - extract SRC/DST IPs from firewall logs
loki.process "syslog" {
  stage.regex {
    expression = "SRC=(?P<src_ip>\\d+\\.\\d+\\.\\d+\\.\\d+)\\s+DST=(?P<dest_ip>\\d+\\.\\d+\\.\\d+\\.\\d+)"
  }

  stage.labels {
    values = {
      src_ip  = "",
      dest_ip = "",
    }
  }

  forward_to = [loki.write.default.receiver]
}

// Write logs to Loki
loki.write "default" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
"""


def render_syslog_ng_config() -> str:
    """Render the syslog-ng configuration."""

    return """@version: 4.0
@include "scl.conf"

source s_local {
\tinternal();
};

source s_network {
\tdefault-network-drivers();
};

destination d_loki {
\tsyslog("127.0.0.1" transport("tcp") port("1514"));
};

log {
\tsource(s_local);
\tsource(s_network);
\tdestination(d_loki);
};
"""


def render_grafana_prometheus_datasource() -> str:
    """Render the Grafana Prometheus datasource provisioning."""

    return """apiVersion: 1
datasources:
  -
    access: proxy
    basicAuth: false
    name: Prometheus
    type: prometheus
    url: "http://prometheus:9090/"
"""


def render_grafana_loki_datasource() -> str:
    """Render the Grafana Loki datasource provisioning."""

    return """apiVersion: 1
datasources:
  -
    access: proxy
    basicAuth: false
    jsonData:
      maxLines: 1000
    name: Loki
    type: loki
    url: "http://loki:3100/"
"""


def render_grafana_dashboard_provisioning() -> str:
    """Render the Grafana dashboard provisioning configuration."""

    return """apiVersion: 1

providers:
- name: 'PerformanceOverviewDashboards'
  orgId: 1
  folder: 'Performance Overview'
  type: file
  disableDeletion: false
  editable: true
  updateIntervalSeconds: 10
  options:
    path: /var/lib/grafana/dashboards/performance_overview
"""


def render_monitoring_env() -> str:
    """Render environment variables for Grafana."""

    return """GF_LOG_MODE=console file
GF_ANALYTICS_REPORTING_ENABLED=false
GF_ANALYTICS_CHECK_FOR_UPDATES=true
GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=true
"""


def render_fetch_monitoring_dashboards_script(plan: DeploymentPlan) -> str:
    """Render a script that fetches Grafana dashboards from the pinned upstream repo."""

    ref = plan.monitoring.ref
    base_url = (
        "https://raw.githubusercontent.com/"
        f"nullroute-commits/enter-the-metrics/{ref}"
        "/grafana/data/dashboards/performance_overview"
    )

    return f"""#!/bin/sh
set -eu

# Fetch Grafana performance overview dashboards from the pinned
# enter-the-metrics repository ({plan.monitoring.repository} @ {ref}).
# Dashboards are provisioned into Grafana via the dashboard provider
# configuration in configuration/monitoring/grafana/provisioning/dashboards/.

DASHBOARD_DIR="${{1:-configuration/monitoring/grafana/dashboards/performance_overview}}"
mkdir -p "$DASHBOARD_DIR"

BASE_URL="{base_url}"

DASHBOARDS="
performance_overview_docker.json
performance_overview_grafana.json
performance_overview_loki.json
performance_overview_prometheus.json
prometheus_node_exporter.json
"

for dashboard in $DASHBOARDS; do
  echo "Fetching $dashboard ..."
  if command -v wget >/dev/null 2>&1; then
    if ! wget -q -O "$DASHBOARD_DIR/$dashboard" "$BASE_URL/$dashboard"; then
      echo "WARNING: Failed to fetch $dashboard; continuing without it" >&2
      rm -f "$DASHBOARD_DIR/$dashboard"
    fi
  elif command -v curl >/dev/null 2>&1; then
    if ! curl -fsSL -o "$DASHBOARD_DIR/$dashboard" "$BASE_URL/$dashboard"; then
      echo "WARNING: Failed to fetch $dashboard; continuing without it" >&2
      rm -f "$DASHBOARD_DIR/$dashboard"
    fi
  else
    echo "ERROR: Neither wget nor curl is available" >&2
    exit 1
  fi
done

echo "Dashboards fetched to $DASHBOARD_DIR"
"""


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
    adjacent_service_sections = [
        (
            f"### {service.category.title()}\n\n"
            f"- Primary: [{service.primary_solution}]({service.primary_url})\n"
            f"- Why: {service.rationale}\n"
            f"- Alternatives: {', '.join(service.alternatives)}\n"
            f"- Integration: {service.integration_notes}"
        )
        for service in plan.adjacent_services
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
- ORB config: `configuration/orb/agent.yaml`
- ORB default schedule: `@every 60m`
- ORB agent: optional `orb-discovery` profile using `netboxlabs/orb-agent` in host networking mode.
- Diode stack: `diode-auth`, `diode-ingester`, and `diode-reconciler` services.
- Diode credential setup: `diode-credential-setup` one-shot service
  auto-creates the `diode` admin user and API token after superuser sync.

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

## Monitoring Stack (enter-the-metrics)

- Profile: `monitoring`
- Source: {plan.monitoring.repository} @ {plan.monitoring.ref}
- Services: Grafana, Prometheus, Loki, Alloy, syslog-ng, node-exporter, snmp-exporter, cAdvisor
- Grafana: {plan.monitoring.grafana_image}
- Prometheus: {plan.monitoring.prometheus_image}
- Loki: {plan.monitoring.loki_image}
- Alloy: {plan.monitoring.alloy_image}
- syslog-ng: {plan.monitoring.syslog_ng_image}
- node-exporter: {plan.monitoring.node_exporter_image}
- snmp-exporter: {plan.monitoring.snmp_exporter_image}
- cAdvisor: {plan.monitoring.cadvisor_image}
- Rationale: {plan.monitoring.rationale}

## Identity Services (Authentik + Ory Hydra)

- Authentik profile: `identity` (opt-in)
- Hydra: starts by default (required by diode-auth)
- Hydra image: {plan.identity.hydra_image}
- Authentik image: {plan.identity.authentik_image}
- Network: identity (172.30.0.160/27)
- Default services: hydra, hydra-migrate, hydra-bootstrap-clients, hydra-postgres
- Profile services: authentik-server, authentik-worker, authentik-postgres
- Rationale: {plan.identity.rationale}

### Start Authentik identity provider (optional)

```bash
# 1. Enable the identity Compose profile
docker compose --profile identity up -d

# 2. Activate Authentik SSO in Traefik (rename the disabled overlay)
mv configuration/traefik/dynamic-identity.yml.disabled \\
   configuration/traefik/dynamic-identity.yml
```

Hydra starts automatically with the default stack because diode-auth is
hard-coupled to the Ory Hydra Admin API for client credential grants.
The `hydra-bootstrap-clients` init container automatically registers the
Diode and NetBox-to-Diode OAuth2 clients on first start.

Authentik provides the user-facing SSO/OIDC identity provider for NetBox
and is available as an opt-in `identity` profile.  The base Traefik
config routes NetBox traffic directly to the WAF without SSO.  To enable
Authentik forward-auth, rename `dynamic-identity.yml.disabled` to
`dynamic-identity.yml` in the Traefik config directory (see above).

## Recommended Adjacent FOSS Services

{chr(10).join(adjacent_service_sections)}

## Privacy Controls

- Bootstrap username: {plan.admin_privacy.bootstrap_username}
- Bootstrap email: {plan.admin_privacy.bootstrap_email}
- Rotation required: {plan.admin_privacy.rotation_required}
- Rationale: {plan.admin_privacy.rationale}

## First Start

### 1. Populate secrets

Generate real secret values from the examples:

```bash
cd secrets
openssl rand -hex 32 > api_token_pepper_1
openssl rand -base64 24 | tr -d '\\n' > db_password
openssl rand -hex 32 > secret_key
openssl rand -base64 24 | tr -d '\\n' > superuser_api_token
cp superuser_name.example superuser_name
openssl rand -base64 18 | tr -d '\\n' > superuser_password
cd ..
```

Keep `secrets/superuser_name` aligned with the pseudonymous bootstrap account unless
you intentionally rotate it before first start.

### 2. Build images

```bash
docker compose build
```

This builds the custom NetBox plugin image used by `netbox`, `netbox-worker`, and
the geo-foss import sidecar image.

### 3. Start the stack

```bash
docker compose up -d
```

On first boot, NetBox runs database migrations before becoming healthy. Dependent
services (workers, WAF, Traefik, superuser sync) wait for the NetBox health check.
This typically takes 2\u20135 minutes. Monitor progress with:

```bash
docker compose ps
docker logs {plan.deployment_name}-netbox-1 --tail 20
```

Once NetBox shows `(healthy)`, all dependent containers start automatically. If any
remain in `Created` state, re-run `docker compose up -d`.

The `diode-credential-setup` service runs automatically after the superuser sync and
creates the `diode` admin user required by the Diode plugin. This is idempotent and
runs on every stack start.

### 4. Access NetBox

NetBox is available at **https://localhost** (port 443, self-signed TLS certificate).

- **Username**: `{plan.admin_privacy.bootstrap_username}`
- **Password**: the value in `secrets/superuser_password`

The bootstrap account is intended only for first login and RBAC setup \u2014 rotate or
disable it after creating named operator accounts.

### 5. Import device-type library (optional)

```bash
docker compose --profile device-type-library-import run --rm device-type-library-import
```

The one-shot importer downloads the pinned `devicetype-library` archive, parses YAML
definitions, and creates objects through `/api/dcim/` REST endpoints. The import is
idempotent \u2014 existing objects are skipped.

### 6. Import geographic data (optional)

```bash
docker compose build netbox-geo-foss
docker compose --profile geo-foss-import run --rm netbox-geo-foss
```

Set `GEONAMES_USERNAME` in `env/geo-foss.env` to a valid GeoNames account for live
API data. Without it, the import falls back to an embedded dataset of 64 countries
and ~215 cities.

### 7. Start the monitoring stack (optional)

```bash
./scripts/fetch-monitoring-dashboards.sh
docker compose --profile monitoring up -d
```

The monitoring profile starts Grafana, Prometheus, Loki, Alloy, syslog-ng,
node-exporter, snmp-exporter, and cAdvisor. Run the dashboard fetch script once
to download the Grafana performance overview dashboards from the pinned upstream
repository. Grafana is then available at **http://localhost:3000** with the default
`admin`/`admin` credentials.

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
    (output_dir / "configuration" / "monitoring" / "prometheus").mkdir(parents=True, exist_ok=True)
    (output_dir / "configuration" / "monitoring" / "loki").mkdir(parents=True, exist_ok=True)
    (output_dir / "configuration" / "monitoring" / "alloy").mkdir(parents=True, exist_ok=True)
    (output_dir / "configuration" / "monitoring" / "syslog-ng").mkdir(parents=True, exist_ok=True)
    grafana_prov = output_dir / "configuration" / "monitoring" / "grafana" / "provisioning"
    (grafana_prov / "datasources").mkdir(parents=True, exist_ok=True)
    (grafana_prov / "dashboards").mkdir(parents=True, exist_ok=True)
    grafana_dash = output_dir / "configuration" / "monitoring" / "grafana" / "dashboards"
    (grafana_dash / "performance_overview").mkdir(parents=True, exist_ok=True)
    (output_dir / "env").mkdir(exist_ok=True)
    (output_dir / "secrets").mkdir(exist_ok=True)
    (output_dir / "scripts").mkdir(exist_ok=True)

    files: dict[Path, str] = {
        output_dir / "docker-compose.yml": render_compose(plan),
        output_dir / "Dockerfile-Plugins": render_dockerfile_plugins(plan),
        output_dir / "Dockerfile-GeoFoss": render_geo_foss_dockerfile(plan),
        output_dir / "plugin_requirements.txt": render_plugin_requirements(plan),
        output_dir / "configuration" / "extra.py": render_netbox_extra_py(),
        output_dir / "configuration" / "plugins.py": render_plugins_py(plan),
        output_dir / "configuration" / "traefik" / "dynamic.yml": (
            render_traefik_dynamic_config(plan)
        ),
        output_dir / "configuration" / "traefik" / "dynamic-identity.yml.disabled": (
            render_traefik_identity_config(plan)
        ),
        output_dir / "configuration" / "waf" / "default.conf": render_waf_default_conf(),
        output_dir / "configuration" / "orb" / "agent.yaml": render_orb_agent_config(),
        output_dir / "env" / "netbox.env": render_netbox_env(plan),
        output_dir / "env" / "postgres.env": render_postgres_env(plan),
        output_dir / "env" / "diode.env": render_diode_env(),
        output_dir / "env" / "authentik.env": render_authentik_env(),
        output_dir / "env" / "hydra.env": render_hydra_env(),
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
    }

    if plan.tls.mode != "letsencrypt":
        files[output_dir / "scripts" / "generate-traefik-cert.sh"] = (
            render_traefik_cert_script(plan)
        )
    else:
        files[output_dir / "secrets" / "cf_dns_api_token.example"] = (
            "replace-with-your-cloudflare-dns-api-token\n"
        )

    files.update({
        output_dir / "scripts" / "sync-superuser.sh": render_superuser_sync_script(),
        output_dir / "scripts" / "run-diode-ingester.sh": render_diode_ingester_script(),
        output_dir / "scripts" / "run-diode-reconciler.sh": render_diode_reconciler_script(),
        output_dir / "scripts" / "setup-diode-credential.sh": (
            render_diode_credential_setup_script()
        ),
        output_dir / "scripts" / "authentik-bootstrap-netbox.sh": (
          render_authentik_netbox_bootstrap_script()
        ),
        output_dir / "scripts" / "run-geo-foss-import.sh": render_geo_foss_import_script(),
        output_dir / "scripts" / "import-geo-data.py": render_geo_foss_import_runner(),
        output_dir
        / "scripts"
        / "fetch-monitoring-dashboards.sh": render_fetch_monitoring_dashboards_script(plan),
        output_dir
        / "configuration"
        / "monitoring"
        / "prometheus"
        / "prometheus.yml": render_prometheus_config(),
        output_dir
        / "configuration"
        / "monitoring"
        / "loki"
        / "loki-config.yml": render_loki_config(),
        output_dir
        / "configuration"
        / "monitoring"
        / "alloy"
        / "config.alloy": render_alloy_config(),
        output_dir
        / "configuration"
        / "monitoring"
        / "syslog-ng"
        / "syslog-ng.conf": render_syslog_ng_config(),
        output_dir
        / "configuration"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "datasources"
        / "prometheus.yml": render_grafana_prometheus_datasource(),
        output_dir
        / "configuration"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "datasources"
        / "loki.yml": render_grafana_loki_datasource(),
        output_dir
        / "configuration"
        / "monitoring"
        / "grafana"
        / "provisioning"
        / "dashboards"
        / "performance_overview.yml": render_grafana_dashboard_provisioning(),
        output_dir / "env" / "monitoring.env": render_monitoring_env(),
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
        output_dir / "secrets" / "diode_redis_password.example": (
          "replace-with-a-strong-diode-redis-password\n"
        ),
        output_dir / "secrets" / "netbox_to_diode.example": (
          "replace-with-the-netbox-to-diode-client-secret\n"
        ),
        output_dir / "secrets" / "diode_client_id.example": (
          "netbox-to-diode\n"
        ),
        output_dir / "secrets" / "diode_client_secret.example": (
          "replace-with-the-diode-client-secret-for-orb\n"
        ),
        output_dir / "secrets" / "authentik_secret_key.example": (
          "replace-with-a-strong-authentik-secret-key\n"
        ),
        output_dir / "secrets" / "authentik_pg_password.example": (
          "replace-with-authentik-postgres-password\n"
        ),
        output_dir / "secrets" / "hydra_pg_password.example": (
          "replace-with-hydra-postgres-password\n"
        ),
        output_dir / "secrets" / "hydra_system_secret.example": (
          "replace-with-hydra-system-secret\n"
        ),
    })

    written: list[Path] = []
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")
        if path.suffix in {".sh", ".py"}:
            path.chmod(0o755)
        written.append(path)
    return written
