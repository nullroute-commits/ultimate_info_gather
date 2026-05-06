# Generated Bundle

This page provides a complete listing of all files, services, and profiles produced by the deployment factory renderer.

## Generated Files

### Core Files

| File | Description |
|------|-------------|
| `docker-compose.yml` | Full stack with all core, profiled, and init services |
| `Dockerfile-Plugins` | Custom NetBox image with plugin requirements and migrations |
| `Dockerfile-GeoFoss` | Local build of the netbox-geo-foss import sidecar |
| `plugin_requirements.txt` | Pinned plugin package versions |
| `deployment-plan.json` | Serialized deployment plan for audit and reproducibility |
| `README.md` | Bundle-specific documentation with deployment instructions |

### Configuration Files

| File | Description |
|------|-------------|
| `configuration/plugins.py` | NetBox `PLUGINS` and `PLUGINS_CONFIG` |
| `configuration/extra.py` | NetBox remote-auth settings for Authentik SSO |
| `configuration/traefik/dynamic.yml` | Traefik TLS certificates and routing rules |
| `configuration/traefik/dynamic-identity.yml.disabled` | Traefik Authentik forward-auth overlay (rename to enable) |
| `configuration/waf/default.conf` | OWASP ModSecurity CRS nginx reverse proxy |
| `configuration/orb/agent.yaml` | ORB agent configuration |
| `configuration/monitoring/prometheus/prometheus.yml` | Prometheus scrape targets |
| `configuration/monitoring/loki/loki-config.yml` | Loki log aggregation |
| `configuration/monitoring/alloy/config.alloy` | Alloy log agent |
| `configuration/monitoring/syslog-ng/syslog-ng.conf` | syslog-ng forwarding |
| `configuration/monitoring/grafana/provisioning/datasources/prometheus.yml` | Grafana Prometheus datasource |
| `configuration/monitoring/grafana/provisioning/datasources/loki.yml` | Grafana Loki datasource |
| `configuration/monitoring/grafana/provisioning/dashboards/performance_overview.yml` | Dashboard provisioning |

### Environment Files

| File | Description |
|------|-------------|
| `env/netbox.env` | NetBox application settings |
| `env/postgres.env` | PostgreSQL configuration |
| `env/diode.env` | Diode service settings (contains `replace-me` placeholders) |
| `env/orb.env` | ORB agent settings |
| `env/device-type-library-import.env` | Library import settings |
| `env/geo-foss.env` | Geographic data import settings |
| `env/monitoring.env` | Grafana environment variables |
| `env/authentik.env` | Authentik identity provider settings |
| `env/hydra.env` | Ory Hydra OAuth2 server settings |

### Scripts

| File | Description |
|------|-------------|
| `scripts/sync-superuser.sh` | Creates bootstrap superuser and writes v2 API token |
| `scripts/run-device-type-library-import.sh` | Device-type library import runner |
| `scripts/import-device-type-library.py` | REST API importer for device types |
| `scripts/run-diode-ingester.sh` | Diode ingester entrypoint |
| `scripts/run-diode-reconciler.sh` | Diode reconciler entrypoint |
| `scripts/setup-diode-credential.sh` | Provisions Diode OAuth2 client credentials |
| `scripts/run-geo-foss-import.sh` | Geographic data import runner |
| `scripts/import-geo-data.py` | pynetbox-based geographic region import |
| `scripts/fetch-monitoring-dashboards.sh` | Downloads Grafana dashboards from pinned upstream |
| `scripts/authentik-bootstrap-netbox.sh` | Configures NetBox as an OAuth2 app in Authentik |
| `scripts/generate-traefik-cert.sh` | Self-signed TLS cert generation (self-signed mode only) |

### Secret Placeholders

| File | Description |
|------|-------------|
| `secrets/.gitignore` | Prevents real secrets from being committed |
| `secrets/db_password.example` | PostgreSQL password |
| `secrets/api_token_pepper_1.example` | NetBox API token pepper |
| `secrets/secret_key.example` | NetBox secret key |
| `secrets/superuser_name.example` | Bootstrap admin username |
| `secrets/superuser_password.example` | Bootstrap admin password |
| `secrets/superuser_api_token.example` | Bootstrap API token |
| `secrets/diode_redis_password.example` | Diode Redis password |
| `secrets/diode_client_id.example` | Diode OAuth2 client ID |
| `secrets/diode_client_secret.example` | Diode OAuth2 client secret |
| `secrets/netbox_to_diode.example` | NetBox-to-Diode client secret |
| `secrets/authentik_secret_key.example` | Authentik secret key |
| `secrets/authentik_pg_password.example` | Authentik PostgreSQL password |
| `secrets/authentik_admin_password.example` | Authentik akadmin bootstrap password |
| `secrets/grafana_admin_password.example` | Grafana admin password |
| `secrets/hydra_pg_password.example` | Hydra PostgreSQL password |
| `secrets/hydra_system_secret.example` | Hydra system secret |
| `secrets/cf_dns_api_token.example` | Cloudflare DNS API token (Let's Encrypt mode only) |

!!! note "Conditional files"
    - In self-signed mode: `scripts/generate-traefik-cert.sh` is generated.
    - In Let's Encrypt mode: `secrets/cf_dns_api_token.example` is generated instead.

## Compose Services

### Core Stack (Always Started)

| Service | Image | Description |
|---------|-------|-------------|
| `traefik` | `traefik:v3.6.13` | TLS reverse proxy (port 443) |
| `waf` | `owasp/modsecurity-crs:4.25.0-nginx-lts` | OWASP ModSecurity CRS WAF sidecar |
| `postgres` | Track-dependent | PostgreSQL database |
| `valkey` | Track-dependent | Valkey cache and task queue |
| `netbox` | `<deployment-name>:local` | NetBox application |
| `netbox-worker` | `<deployment-name>:local` | NetBox RQ worker (1 or more) |
| `netbox-init` | `<deployment-name>:local` | Bootstrap superuser, token mint, and Diode credential setup (one-shot init) |
| `diode-auth` | `netboxlabs/diode-auth:1.12.0` | Diode authentication service |
| `diode-ingester` | `netboxlabs/diode-ingester:1.13.0` | Diode ingestion service |
| `diode-reconciler` | `netboxlabs/diode-reconciler:1.13.0` | Diode reconciliation service |
| `diode-proxy` | `nginx:1.27-alpine` | HTTP/gRPC mux for Diode token and ingest traffic |
| `diode-token-adapter` | `python:3.11-alpine` | Scope-claim translation adapter for Hydra JWT compatibility |
| `hydra-postgres` | Track-dependent | Dedicated Postgres for Hydra |
| `hydra-migrate` | `oryd/hydra:v2.3.0` | Hydra database migration |
| `hydra` | `oryd/hydra:v2.3.0` | OAuth2/OIDC server for Diode |
| `hydra-bootstrap-clients` | `oryd/hydra:v2.3.0` | Diode OAuth2 client provisioning |

!!! note "Self-signed mode only"
    In self-signed mode, a `traefik-certgen` init container runs before Traefik to generate the TLS certificate.

### Profiled Services (Opt-In)

| Service | Profile | Image | Description |
|---------|---------|-------|-------------|
| `device-type-library-import` | `device-type-library-import` | `<deployment-name>:local` | One-shot device-type library import |
| `netbox-geo-foss` | `geo-foss-import` | Built locally | Geographic data import sidecar |
| `orb-agent` | `orb-discovery` | `netboxlabs/orb-agent:2.7.0` | ORB network discovery agent |
| `wazuh-agent` | `security-observability` | `wazuh/wazuh-agent:4.14.4` | Security observability agent |
| `grafana` | `monitoring` | `grafana/grafana:12.4.2` | Dashboard visualization |
| `prometheus` | `monitoring` | `prom/prometheus:v3.11.0` | Metrics collection |
| `loki` | `monitoring` | `grafana/loki:3.7.1` | Log aggregation |
| `alloy` | `monitoring` | `grafana/alloy:v1.15.0` | Log shipping agent (syslog → Loki) |
| `syslog-ng` | `monitoring` | `balabit/syslog-ng:4.11.0` | Syslog forwarding |
| `node-exporter` | `monitoring` | `prom/node-exporter:v1.11.1` | Host system metrics |
| `snmp-exporter` | `monitoring` | `prom/snmp-exporter:v0.30.1` | SNMP device metrics |
| `cadvisor` | `monitoring` | `gcr.io/cadvisor/cadvisor:v0.52.1` | Container metrics |
| `monitoring-dashboard-init` | `monitoring` | `alpine:3.23` | Grafana dashboard provisioning |
| `authentik-server` | `identity` | `ghcr.io/goauthentik/server:2026.2.2` | SSO/OIDC identity provider |
| `authentik-worker` | `identity` | `ghcr.io/goauthentik/server:2026.2.2` | Authentik background worker |
| `authentik-postgres` | `identity` | Track-dependent | Dedicated Postgres for Authentik |
| `authentik-bootstrap-netbox` | `identity` | `ghcr.io/goauthentik/server:2026.2.2` | NetBox OAuth2 app configuration |

## Docker Volumes

| Volume | Purpose |
|--------|---------|
| `netbox-media` | NetBox uploaded media |
| `netbox-reports` | NetBox generated reports |
| `netbox-scripts` | NetBox custom scripts |
| `postgres-data` | PostgreSQL data |
| `valkey-data` | Valkey persistent data |
| `token-store` | Shared v2 API token for sidecars |
| `traefik-certs` | Self-signed TLS certificates (self-signed mode) |
| `acme-data` | ACME account and certificates (Let's Encrypt mode) |
| `geo-foss-cache` | Downloaded geographic datasets |
| `grafana-data` | Grafana dashboard and settings storage (monitoring profile) |
| `grafana-dashboards` | Provisioned Grafana dashboards (monitoring profile) |
| `prometheus-data` | Prometheus metrics storage (monitoring profile) |
| `authentik-pg-data` | Authentik PostgreSQL data (identity profile) |
| `authentik-data` | Authentik application data (identity profile) |
| `hydra-pg-data` | Hydra PostgreSQL data |

## Directory Structure

```
<output-dir>/
├── docker-compose.yml
├── Dockerfile-Plugins
├── Dockerfile-GeoFoss
├── plugin_requirements.txt
├── deployment-plan.json
├── README.md
├── configuration/
│   ├── extra.py
│   ├── plugins.py
│   ├── traefik/
│   │   ├── dynamic.yml
│   │   └── dynamic-identity.yml.disabled
│   ├── waf/
│   │   └── default.conf
│   ├── orb/
│   │   └── agent.yaml
│   └── monitoring/
│       ├── prometheus/
│       │   └── prometheus.yml
│       ├── loki/
│       │   └── loki-config.yml
│       ├── alloy/
│       │   └── config.alloy
│       ├── syslog-ng/
│       │   └── syslog-ng.conf
│       └── grafana/
│           ├── dashboards/
│           │   └── performance_overview/
│           └── provisioning/
│               ├── datasources/
│               │   ├── prometheus.yml
│               │   └── loki.yml
│               └── dashboards/
│                   └── performance_overview.yml
├── env/
│   ├── netbox.env
│   ├── postgres.env
│   ├── diode.env
│   ├── orb.env
│   ├── device-type-library-import.env
│   ├── geo-foss.env
│   ├── monitoring.env
│   ├── authentik.env
│   └── hydra.env
├── scripts/
│   ├── sync-superuser.sh
│   ├── run-device-type-library-import.sh
│   ├── import-device-type-library.py
│   ├── run-diode-ingester.sh
│   ├── run-diode-reconciler.sh
│   ├── setup-diode-credential.sh
│   ├── run-geo-foss-import.sh
│   ├── import-geo-data.py
│   ├── fetch-monitoring-dashboards.sh
│   ├── authentik-bootstrap-netbox.sh
│   └── generate-traefik-cert.sh  (self-signed mode)
└── secrets/
    ├── .gitignore
    ├── *.example
    └── cf_dns_api_token.example  (Let's Encrypt mode)
```
