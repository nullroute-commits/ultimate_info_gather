# NetBox Deployment Factory

This repository turns `ultimate_info_gather` JSON output into a reproducible NetBox deployment bundle that follows current NetBox Labs and official netbox-docker practices.

All local CI/CD operations are Docker-localized. The host only needs Docker Compose; linting, type checking, tests, and bundle generation run inside the CI image defined in this repository.

The generated bundle is opinionated:

- NetBox is treated as the source of truth for topology, IPAM, and network automation data.
- The deployment baseline follows the official netbox-docker plugin workflow rather than ad hoc container patterns.
- Plugin enablement is strict: topology and BGP are enabled because they have visible NetBox 4.5 compatibility from official NetBox Community sources.
- Requested plugins are enabled in the generated deployment using upstream compatibility metadata.
- The bootstrap superuser is pseudonymous and secret-file backed so the initial administrative identity is not tied to a human username.
- The community device-type library is included as a separate pinned import workflow that uses the NetBox REST API for idempotent creation of manufacturers, device types (with component templates), module types, and rack types.
- ORB Discovery is generated as an optional profile using the official `netboxlabs/orb-agent` image and an `agent.yaml` config.
- A Traefik v3.2 reverse proxy terminates TLS at the edge and routes traffic through an OWASP ModSecurity CRS WAF sidecar before reaching NetBox.
- Docker networks are scoped into isolated segments (edge, app, data, security) with explicit CIDR allocations sized for the required host counts.
- Valkey replaces Redis as the cache and task-queue backend.
- Diode is deployed as `diode-auth`, `diode-ingester`, and `diode-reconciler` companion services.
- TLS termination supports two modes: auto-generated self-signed certificates (default) or Let's Encrypt ACME via DNS-01 Cloudflare challenge when an FQDN is provided.
- Geographic data is imported as a three-tier Region hierarchy (continent → country → city) via a one-shot sidecar using the pynetbox REST API.
- A complete monitoring stack (Grafana, Prometheus, Loki, Promtail, syslog-ng, node_exporter, snmp_exporter, cAdvisor) is available as an optional `monitoring` Compose profile, based on the [enter-the-metrics](https://github.com/nullroute-commits/enter-the-metrics) project.

## Version Pins

- NetBox: `4.5.4` as the highest current stable `4.5.x` core patch release
- netbox-docker workflow baseline: `4.0.1`
- Alpine lifecycle reference: `3.23.3`
- Debian lifecycle reference: `13.3 (Trixie)`
- Traefik: `v3.2`
- WAF: `owasp/modsecurity-crs:nginx` (OWASP Core Rule Set with nginx)
- Valkey: pinned per lifecycle track (replaces Redis)
- Diode auth: `netboxlabs/diode-auth:1.12.0`
- Diode ingester: `netboxlabs/diode-ingester:1.13.0`
- Diode reconciler: `netboxlabs/diode-reconciler:1.13.0`
- ORB agent: `netboxlabs/orb-agent:2.7.0`
- Wazuh agent: `wazuh/wazuh-agent:4.14.3`
- Topology plugin: `netbox-topology-views==4.5.0`
- BGP plugin: `netbox-bgp==0.18.0`
- DNS plugin: `netbox-plugin-dns==1.5.3`
- Config diff plugin: `netbox-config-diff==2.14.0`
- Floorplan plugin: `netbox-floorplan-plugin==0.9.0`
- Inventory plugin: `netbox-inventory==2.5.0`
- Device type library repository: `netbox-community/devicetype-library` pinned by commit `cf50cfe`
- Geographic data sidecar: built locally from `netbox-geo-foss` pinned at commit `50c3c16`
- Monitoring stack: based on `enter-the-metrics` pinned at commit `abb9825`
  - Grafana: `grafana/grafana:11.4.0`
  - Prometheus: `prom/prometheus:v2.54.1`
  - Loki: `grafana/loki:3.2.1`
  - Promtail: `grafana/promtail:3.2.1`
  - syslog-ng: `balabit/syslog-ng:4.11.0`
  - node-exporter: `prom/node-exporter:v1.8.2`
  - snmp-exporter: `prom/snmp-exporter:v0.27.0`
  - cAdvisor: `gcr.io/cadvisor/cadvisor:v0.51.0`

## Full Deployment Walkthrough

This section covers every step from a clean checkout to a running NetBox instance with imported device types and geographic data.

### Step 1 — Generate a host report

Run `ultimate_info_gather` from the repository root to produce a JSON report describing the target host:

```bash
python3 main.py -o ./generated-report -f json
```

The report path (e.g. `generated-report/report_20260309_154959.json`) is used as input to the factory.

### Step 2 — Build the factory CI image

```bash
cd netbox_deployment_factory
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml build factory
```

### Step 3 — Generate the deployment bundle

Debian track (default):

```bash
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --track debian \
  --deployment-name netbox-deploy
```

Alpine track:

```bash
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --track alpine \
  --deployment-name netbox-deploy
```

Let's Encrypt TLS (requires an FQDN and Cloudflare DNS):

```bash
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --track debian \
  --deployment-name netbox-deploy \
  --fqdn netbox.example.com \
  --acme-email admin@example.com
```

The `/host-root/` prefix maps to the parent of `netbox_deployment_factory/` via the CI Compose bind mount.

### Step 4 — Populate secrets

Enter the generated bundle directory and create real secret files from the examples:

```bash
cd generated/netbox-deploy/secrets
openssl rand -hex 32 > api_token_pepper_1
openssl rand -base64 24 | tr -d '\n' > db_password
openssl rand -hex 32 > secret_key
openssl rand -base64 24 | tr -d '\n' > superuser_api_token
cp superuser_name.example superuser_name
openssl rand -base64 18 | tr -d '\n' > superuser_password
cd ..
```

Keep `superuser_name` aligned with the pseudonymous bootstrap account unless you intentionally change it before first start.

### Step 5 — Build images

Build the custom NetBox plugin image and the geo-foss sidecar:

```bash
docker compose build
```

### Step 6 — Start the stack

```bash
docker compose up -d
```

On first boot, NetBox runs database migrations before it becomes healthy. Dependent services (workers, WAF, Traefik, superuser sync) wait for the NetBox health check to pass. This typically takes 2–5 minutes depending on the host.

Check progress:

```bash
docker compose ps
docker logs netbox-deploy-netbox-1 --tail 20
```

Once NetBox shows `(healthy)`, all dependent containers should start automatically. If any remain in `Created` state, re-run:

```bash
docker compose up -d
```

### Step 6b — Populate Cloudflare DNS token (Let's Encrypt only)

If the bundle was generated with `--fqdn`, create the Cloudflare API token secret:

```bash
cd generated/netbox-deploy/secrets
echo -n 'your-cloudflare-dns-api-token' > cf_dns_api_token
cd ..
```

The token needs `Zone:DNS:Edit` permission for the zone containing the FQDN. See the `cf_dns_api_token.example` file for details.

### Step 7 — Access NetBox

NetBox is available at **https://<host-ip>** (port 443).

- **Self-signed mode** (default): The TLS certificate is auto-generated by the `traefik-certgen` init container.
- **Let's Encrypt mode** (`--fqdn`): Traefik obtains a trusted certificate via ACME DNS-01 challenge. Access NetBox at `https://<fqdn>` instead.

When the generator runs inside WSL or another guest environment, pass `--host-ip <windows-or-lan-ip>` so published ports, public URLs, and identity redirects use the real host address instead of the guest NAT address.

Log in with:
- **Username**: the value in `secrets/superuser_name` (e.g. `bootstrap-10f19331c8`)
- **Password**: the value in `secrets/superuser_password`

The bootstrap account is intended only for first login and RBAC setup — rotate or disable it after creating named operator accounts.

### Step 8 — Import device-type library (optional)

```bash
docker compose --profile device-type-library-import run --rm device-type-library-import
```

### Step 9 — Import geographic data (optional)

```bash
docker compose build netbox-geo-foss
docker compose --profile geo-foss-import run --rm netbox-geo-foss
```

Set `GEONAMES_USERNAME` in `env/geo-foss.env` to a valid GeoNames account for live API data. Without it, the import falls back to an embedded dataset of 64 countries and ~215 cities.

### Step 10 — Start the monitoring stack (optional)

```bash
./scripts/fetch-monitoring-dashboards.sh
docker compose --profile monitoring up -d
```

This starts the full monitoring stack: Grafana, Prometheus, Loki, Promtail, syslog-ng, node-exporter, snmp-exporter, and cAdvisor. Run the dashboard fetch script once to download the Grafana performance overview dashboards from the pinned upstream repository.

Grafana is available at **http://localhost:3000** with the default `admin`/`admin` credentials. Change the password on first login.

Prometheus scrapes metrics from the monitoring services and NetBox stack services on the `data` network. To forward syslogs to syslog-ng, configure the source device to send to `<host-ip>:514` (UDP) or `<host-ip>:601` (TCP).

## Usage (Factory Only)

The commands below are equivalent to Steps 2–3 above and are included for quick reference.

Generate a Debian bundle through the localized Docker workflow:

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --track debian \
  --deployment-name netbox-deploy
```

To generate the Alpine track instead:

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --track alpine \
  --deployment-name netbox-deploy
```

Additional planning flags exposed by the current CLI:

```bash
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --cidr-mode dynamic \
  --edge-hosts 60 \
  --app-hosts 30 \
  --data-hosts 12 \
  --security-hosts 8 \
  --worker-containers 3
```

- `--cidr-mode {deterministic,dynamic}` selects fixed or host-capacity-based Docker subnet allocation.
- `--edge-hosts`, `--app-hosts`, `--data-hosts`, and `--security-hosts` size each network segment when `--cidr-mode dynamic` is used.
- `--worker-containers` overrides the host-derived number of NetBox worker containers.
- `--fqdn` sets the deployment FQDN. When provided, Traefik uses Let's Encrypt ACME DNS-01 via Cloudflare instead of a self-signed certificate. Requires `--acme-email`.
- `--acme-email` sets the email address for Let's Encrypt ACME registration. Required when `--fqdn` is provided.

## What Gets Generated

- `docker-compose.yml` — full stack including Traefik, WAF, NetBox, Postgres, Valkey, Diode auth/ingester/reconciler, workers, superuser sync, and profiled sidecars/services (`orb-discovery`, `device-type-library-import`, `geo-foss-import`, `security-observability`, `monitoring`)
- `Dockerfile-Plugins` — custom NetBox image with plugin requirements and migrations
- `Dockerfile-GeoFoss` — local build of the netbox-geo-foss import sidecar
- `plugin_requirements.txt`
- `configuration/plugins.py`
- `configuration/traefik/dynamic.yml` — Traefik TLS certs and routes through the WAF (self-signed mode includes static cert references; Let's Encrypt mode uses `certResolver` on routers)
- `configuration/waf/default.conf` — OWASP ModSecurity CRS nginx reverse proxy to NetBox
- `configuration/orb/agent.yaml` — ORB agent configuration
- `configuration/monitoring/prometheus/prometheus.yml` — Prometheus scrape configuration
- `configuration/monitoring/loki/loki-config.yml` — Loki log aggregation configuration
- `configuration/monitoring/promtail/promtail-config.yml` — Promtail log agent configuration
- `configuration/monitoring/syslog-ng/syslog-ng.conf` — syslog-ng forwarding configuration
- `configuration/monitoring/grafana/provisioning/datasources/prometheus.yml` — Grafana Prometheus datasource
- `configuration/monitoring/grafana/provisioning/datasources/loki.yml` — Grafana Loki datasource
- `configuration/monitoring/grafana/provisioning/dashboards/performance_overview.yml` — Grafana dashboard provisioning
- `env/netbox.env`
- `env/postgres.env`
- `env/diode.env`
- `env/orb.env`
- `env/device-type-library-import.env`
- `env/geo-foss.env`
- `env/monitoring.env` — Grafana environment variables
- `scripts/generate-traefik-cert.sh` — self-signed TLS cert with SAN entries for localhost, hostname, and internal names (omitted in Let's Encrypt mode)
- `secrets/cf_dns_api_token.example` — Cloudflare DNS API token placeholder (Let's Encrypt mode only)
- `scripts/sync-superuser.sh` — creates the pseudonymous superuser and writes the full v2 API token to `token-store`
- `scripts/run-device-type-library-import.sh`
- `scripts/import-device-type-library.py`
- `scripts/run-diode-ingester.sh`
- `scripts/run-diode-reconciler.sh`
- `scripts/run-geo-foss-import.sh` — reads the v2 token from `token-store` and launches the import
- `scripts/import-geo-data.py` — pynetbox-based import of continents, countries, and cities as NetBox Regions
- `scripts/fetch-monitoring-dashboards.sh` — downloads Grafana dashboards from pinned upstream repository
- `secrets/*.example`
- `deployment-plan.json`
- `README.md` summarizing the generated bundle

## Standards

- Official NetBox plugin pattern: install package, add it to `PLUGINS`, configure under `PLUGINS_CONFIG`, run migrations, run `collectstatic`
- Official netbox-docker workflow: build a custom plugin image and keep plugin configuration additive
- NetBox Labs operating model: NetBox remains the central source of truth for modeling, automation, and security-sensitive inventory workflows
- CI/CD execution is Docker-localized: GitHub Actions and local validation both invoke Docker Compose services instead of running Python tooling directly on the host or runner
- API token creation is enabled through a generated `api_token_pepper_1` secret so NetBox stays aligned with the current token model

All validation commands are expected to run via Docker Compose (`docker compose -f docker-compose.ci.yml ...`).

## Privacy Model

The generated deployment uses a pseudonymous bootstrap admin identity:

- Username is derived from the source report ID instead of a person name.
- Email uses the reserved `.invalid` domain.
- Credentials are expected only in local Docker secret files.
- A dedicated `api_token_pepper_1` secret is generated so NetBox can issue v2 API tokens.
- Database and bootstrap-admin secrets are separated into distinct files.
- The superuser-sync service writes the full v2 token (`nbt_<key>.<plaintext>`) to a `token-store` volume so sidecar services (geo-foss) can authenticate without direct access to the raw secret.
- The import service runs as a separate one-shot workload, but the default generated wiring reuses the bootstrap secret set unless you override the import username.
- The bootstrap account is intended only for first login, RBAC setup, and immediate rotation or disablement.

Before the first `docker compose up -d`:

1. Run `docker compose build` to build the local NetBox plugin image used by
  `netbox` and `netbox-worker`, and the geo-foss import image.
2. Copy each file in `secrets/*.example` to the same path without the `.example`
   suffix and replace placeholder values with real secrets (see Step 4 in the
   Full Deployment Walkthrough above for concrete `openssl` commands).
3. TLS certificates are auto-generated by the `traefik-certgen` init container on first start (self-signed mode). In Let's Encrypt mode, Traefik obtains certificates automatically via ACME DNS-01 — populate `secrets/cf_dns_api_token` with a Cloudflare API token that has `Zone:DNS:Edit` permission. To supply your own certificate in self-signed mode, place `tls.crt` and `tls.key` in the `traefik-certs` volume.
4. Run `docker compose up -d`. On first boot, NetBox runs migrations before
   becoming healthy (2–5 minutes). Dependent services start automatically
   once the health check passes.
5. Access NetBox at **https://localhost** (port 443, self-signed TLS certificate).
   Log in with the pseudonymous bootstrap credentials from `secrets/superuser_name`
   and `secrets/superuser_password`.

## Least Privilege

- Traefik is the only service with published host ports (443 always; 80 added in Let's Encrypt mode for HTTP→HTTPS redirect). All other services communicate over internal Docker networks.
- The OWASP ModSecurity CRS WAF inspects HTTP traffic before it reaches NetBox, blocking common web attacks.
- Docker networks are scoped into five isolated segments:
  - **edge**: Traefik and WAF only
  - **app**: WAF and NetBox only
  - **data**: NetBox, Postgres, Valkey, diode-auth, diode-ingester, diode-reconciler, workers, superuser sync, imports, geo-foss, Prometheus (for scraping)
  - **security**: Wazuh agent
  - **monitoring**: Grafana, Prometheus, Loki, Promtail, syslog-ng, node-exporter, snmp-exporter, cAdvisor

## ORB Discovery Profile

The generated ORB service is intentionally profile-gated because upstream Orb discovery requires host networking and elevated packet capabilities.

Run ORB when needed:

```bash
docker compose --profile orb-discovery up -d orb-agent
```

Before running ORB, set Diode client credentials in `configuration/orb/agent.yaml` and keep ORB in dry-run mode unless your Diode auth path is verified:

```bash
client_id: netbox-to-diode
client_secret: replace-me
```

The generated ORB defaults target RFC1918 ranges (`10/8`, `172.16/12`, `192.168/16`), use `schedule: "@every 60m"` in `configuration/orb/agent.yaml`, and keep `dry_run: true` to stabilize discovery when Diode auth endpoints are unavailable.
- Each network has an explicit CIDR allocation sized for its required host count (deterministic mode uses `172.30.0.0/27` through `172.30.0.128/27`; dynamic mode allocates from `172.31.0.0/16`).
- NetBox application services drop all Linux capabilities and enable `no-new-privileges`.
- The device-type-library import runs as a separate one-shot profile inside the NetBox image.
- The importer keeps dropped capabilities and `no-new-privileges`, and downloads the pinned library archive into temporary storage at runtime.
- The importer authenticates against the NetBox REST API using the v2 token from `secrets/superuser_api_token`. If stricter RBAC is required, create a dedicated NetBox user with DCIM add/view permissions and configure a separate token.
- The geo-foss import sidecar reads its API token from the `token-store` volume rather than mounting the raw secret directly.

## Recommended Adjacent FOSS Services

The generator now emits adjacent-service recommendations into the generated deployment README and `deployment-plan.json`. These are intentionally guidance-only integrations: the core NetBox Compose bundle stays focused on NetBox, its data plane, and bundled import/Diode/ORB sidecars.

- **Identity provider**: Prefer **Authentik** for self-hosted OIDC/SAML and flexible login flows. Evaluate **Keycloak** for mature enterprise federation, **ZITADEL** for cloud-native/passwordless-first deployments, and **Authelia** when forward-auth MFA is enough without a full IdP.
- **Password service**: Prefer **Vaultwarden** as a lightweight Bitwarden-compatible vault for operator and bootstrap secrets. Evaluate **Passbolt** when browser-centric team password sharing is the priority.
- **Link service**: Prefer **Linkding** for self-hosted bookmark and runbook curation. Evaluate **Shlink** when internal short URLs and click analytics are required.
- **Cloud service**: Prefer **Nextcloud** for operator files, notes, calendars, and shared documentation. Evaluate **Seafile** when fast file synchronization matters more than broader groupware.

Deploy these services adjacent to the generated NetBox stack behind the same reverse proxy and chosen identity provider, then link them operationally through NetBox RBAC, runbooks, and exported artifacts.

## Device-Type Library Import

The generated bundle includes an optional `device-type-library-import` service. It is pinned to the NetBox community library repository and intended to be run only when you want to import or refresh device and rack types.

```bash
docker compose --profile device-type-library-import run --rm device-type-library-import
```

The one-shot importer downloads the pinned `devicetype-library` archive, parses YAML definitions, and creates objects through `/api/dcim/` REST endpoints using v2 Bearer token authentication. The import is idempotent — existing objects are skipped.

To import only specific vendors:

```bash
docker compose --profile device-type-library-import run \
  -e DEVICE_TYPE_LIBRARY_VENDORS=cisco,juniper \
  device-type-library-import
```

## Geographic Data Import

The generated bundle includes an optional `netbox-geo-foss` service that imports geographic data into NetBox as a three-tier Region hierarchy (continent → country → city) using pynetbox. The image is built locally from a pinned commit of the upstream repository.

```bash
docker compose build netbox-geo-foss
docker compose --profile geo-foss-import run --rm netbox-geo-foss
```

The import creates:
- 7 continent regions (Africa, Asia, Europe, North America, South America, Oceania, Antarctica)
- ~64 country regions as children of their continent
- ~215 major city regions as children of their country

Country and city data is fetched from the GeoNames API when available. When the GeoNames API is unavailable or rate-limited, the import falls back to an embedded dataset of 64 countries and ~215 cities.

Before running, set `GEONAMES_USERNAME` in `env/geo-foss.env` to a valid GeoNames account username. Downloaded geographic datasets are cached in the `geo-foss-cache` volume. The geo-foss service depends on `netbox-superuser-sync` having completed so the v2 API token is available in the `token-store` volume.

## Monitoring Stack

The generated bundle includes an optional monitoring stack based on [enter-the-metrics](https://github.com/nullroute-commits/enter-the-metrics), profiled under `monitoring`. It provides:

- **Grafana**: Dashboard visualization sourcing data from Prometheus and Loki
- **Prometheus**: Metrics collection with scrape targets for Grafana, Loki, Promtail, node-exporter, and cAdvisor
- **Loki**: Log aggregation
- **Promtail**: Log agent that ships logs to Loki
- **syslog-ng**: Syslog forwarder that sends logs to Promtail
- **node-exporter**: Exposes host system metrics (CPU, memory, network, disk) to Prometheus
- **snmp-exporter**: Forwards SNMP traffic from network devices to Prometheus
- **cAdvisor**: Sends Docker container metrics to Prometheus

Start the monitoring stack:

```bash
./scripts/fetch-monitoring-dashboards.sh
docker compose --profile monitoring up -d
```

The dashboard fetch script downloads five preconfigured Grafana performance overview dashboards (Docker, Grafana, Loki, Prometheus, Node Exporter) from the pinned upstream repository. Grafana is available at **http://localhost:3000** with default credentials `admin`/`admin`.

All monitoring services run on the isolated `monitoring` Docker network. Prometheus also joins the `data` network so it can scrape metrics from NetBox stack services. To add custom Prometheus scrape targets, edit `configuration/monitoring/prometheus/prometheus.yml`. To configure SNMP monitoring, add your device targets to the Prometheus config and set the appropriate community string in the snmp-exporter configuration.

To forward syslogs, configure the source device to send to the host IP on port 514 (UDP) or 601 (TCP).

## Let's Encrypt TLS

When the factory is invoked with `--fqdn` and `--acme-email`, the generated bundle switches from self-signed certificates to Let's Encrypt ACME with a DNS-01 Cloudflare challenge:

```bash
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260309_154959.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --deployment-name netbox-deploy \
  --fqdn netbox.example.com \
  --acme-email admin@example.com
```

Changes relative to self-signed mode:

- The `traefik-certgen` init container and `traefik-certs` volume are removed.
- Traefik is configured with `--certificatesresolvers.letsencrypt.acme.dnschallenge.provider=cloudflare` and the registration email.
- Port 80 is published with an HTTP→HTTPS redirect entrypoint.
- An `acme-data` volume persists the ACME account and certificates.
- The Cloudflare DNS API token is read from Docker secret `cf_dns_api_token`.
- `configuration/traefik/dynamic.yml` uses `certResolver: letsencrypt` on routers with the FQDN as the main domain instead of static certificate references.
- `env/netbox.env` adds the FQDN to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- `secrets/cf_dns_api_token.example` is generated instead of `scripts/generate-traefik-cert.sh`.

### Prerequisites

1. A Cloudflare-managed DNS zone for the FQDN.
2. A Cloudflare API token with `Zone:DNS:Edit` permission scoped to the zone.
3. A DNS A/AAAA record pointing the FQDN to the deployment host (or a wildcard record).

### Setup

```bash
cd generated/netbox-deploy/secrets
echo -n 'your-cloudflare-dns-api-token' > cf_dns_api_token
cd ..
docker compose up -d
```

Traefik will request a certificate on first start. The ACME account and certificate are persisted in the `acme-data` volume. Certificate renewal is automatic.

## Validation

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml build
docker compose -f docker-compose.ci.yml run --rm lint
docker compose -f docker-compose.ci.yml run --rm typecheck
docker compose -f docker-compose.ci.yml run --rm test
docker compose -f docker-compose.ci.yml run --rm bundle
```

Setting `LOCAL_UID` and `LOCAL_GID` keeps generated files, caches, and bundle artifacts owned by the invoking host user instead of container root. The generated sample bundle is localized under `.artifacts/ci-example` so the same Docker workflow works both locally and in GitHub Actions.

When the input report lives outside this repository, use the `/host-root/...` path exposed by the CI Compose bind mount.
