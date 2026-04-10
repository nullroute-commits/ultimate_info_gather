# Generated Deployment Plan

## Source

- Report: deploy_output/reports/report.json
- Generator version: 1.0.0
- Deployment name: netbox-prod

## Host Summary

- Hostname: runnervm35a4x
- OS: Ubuntu 24.04.4 LTS (Noble Numbat)
- Kernel: 6.17.0-1010-azure
- Architecture: x86_64
- WSL: False
- Docker capable: True
- Memory total: 16770764800
- Memory available: 14546034688

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

- NetBox: netboxcommunity/netbox:v4.5.7
- PostgreSQL: postgres:18-alpine
- Valkey: valkey/valkey:9-alpine
- Track: alpine
- Lifecycle reference: Alpine Linux 3.23.3

## Enabled Plugins

- netbox_topology_views (netbox-topology-views==4.5.1) [supported-community]
- netbox_bgp (netbox-bgp==0.18.1) [supported-community]
- netbox_dns (netbox-plugin-dns==1.5.5) [supported-community]
- netbox_acls (netbox-acls==2.0.0) [supported-community]
- netbox_reorder_rack (netbox-reorder-rack==1.1.4) [community]
- netbox_diode_plugin (netboxlabs-diode-netbox-plugin==1.9.0) [supported-netboxlabs]
- netbox_proxbox (netbox-proxbox==0.0.10) [community]
- netbox_config_diff (netbox-config-diff==2.14.2) [community]
- netbox_floorplan (netbox-floorplan-plugin==0.9.1) [community]
- netbox_inventory (netbox-inventory==2.5.1) [community]

## Network Plan

- CIDR mode: deterministic
- edge: 172.30.0.0/27 (required hosts: 16)
- app: 172.30.0.32/27 (required hosts: 16)
- data: 172.30.0.64/27 (required hosts: 16)
- security: 172.30.0.96/28 (required hosts: 8)
- monitoring: 172.30.0.128/27 (required hosts: 16)
- identity: 172.30.0.160/27 (required hosts: 16)

## Container Orchestration

- Worker containers: 4
- ORB config: `configuration/orb/agent.yaml`
- ORB default schedule: `@every 60m`
- ORB agent: optional `orb-discovery` profile using `netboxlabs/orb-agent` in host networking mode.
- Diode stack: `diode-auth`, `diode-ingester`, and `diode-reconciler` services.
- Diode credential setup: `diode-credential-setup` one-shot service
  auto-creates the `diode` admin user and API token after superuser sync.

## Device-Type Library

- Library repository: https://github.com/netbox-community/devicetype-library.git
- Library ref: cf50cfe
- Import service: device-type-library-import
- Rationale: Use the NetBox community device-type library as a pinned source and run imports through NetBox core's own bulk-import workflow inside a dedicated one-shot container.

### Least-Privilege Import Permissions

- dcim.add_manufacturer
- dcim.view_manufacturer
- dcim.add_devicetype
- dcim.view_devicetype
- dcim.add_moduletype
- dcim.view_moduletype
- dcim.add_racktype
- dcim.view_racktype
- dcim.add_consoleporttemplate
- dcim.add_consoleserverporttemplate
- dcim.add_powerporttemplate
- dcim.add_poweroutlettemplate
- dcim.add_interfacetemplate
- dcim.add_frontporttemplate
- dcim.add_rearporttemplate
- dcim.add_modulebaytemplate
- dcim.add_devicebaytemplate
- dcim.add_inventoryitemtemplate

## Geographic Data (netbox-geo-foss)

- Build: local (Dockerfile-GeoFoss)
- Repository: https://github.com/nullroute-commits/netbox-geo-foss.git
- Ref: 50c3c16
- Import service: netbox-geo-foss
- Rationale: Standalone geographic data integration sidecar that imports GeoNames, Natural Earth, and OpenStreetMap data into NetBox via the REST API using pynetbox.

## Monitoring Stack (enter-the-metrics)

- Profile: `monitoring`
- Source: https://github.com/nullroute-commits/enter-the-metrics.git @ 706ed92
- Services: Grafana, Prometheus, Loki, Alloy, syslog-ng, node-exporter, snmp-exporter, cAdvisor
- Grafana: grafana/grafana:12.4.2
- Prometheus: prom/prometheus:v3.11.0
- Loki: grafana/loki:3.7.1
- Alloy: grafana/alloy:v1.15.0
- syslog-ng: balabit/syslog-ng:4.11.0
- node-exporter: prom/node-exporter:v1.11.1
- snmp-exporter: prom/snmp-exporter:v0.30.1
- cAdvisor: gcr.io/cadvisor/cadvisor:v0.52.1
- Rationale: Integrated monitoring stack based on https://github.com/nullroute-commits/enter-the-metrics. Provides Grafana dashboards, Prometheus metrics collection, Loki log aggregation, Alloy log shipping, syslog-ng forwarding, node_exporter host metrics, SNMP exporter, and cAdvisor container metrics. All services are profiled under the 'monitoring' Compose profile.

## Identity Services (Authentik + Ory Hydra)

- Authentik profile: `identity` (opt-in)
- Hydra: starts by default (required by diode-auth)
- Hydra image: oryd/hydra:v2.3.0
- Authentik image: ghcr.io/goauthentik/server:2026.2.2
- Network: identity (172.30.0.160/27)
- Default services: hydra, hydra-migrate, hydra-bootstrap-clients, hydra-postgres
- Profile services: authentik-server, authentik-worker, authentik-postgres
- Rationale: Authentik provides a self-hosted OIDC/SAML identity provider for NetBox SSO. Ory Hydra provides the OAuth2/OIDC server required by diode-auth for client-credentials grants. Both are deployed under the 'identity' Compose profile with dedicated Postgres instances and an isolated identity network segment.

### Start Authentik identity provider (optional)

```bash
# 1. Enable the identity Compose profile
docker compose --profile identity up -d

# 2. Activate Authentik SSO in Traefik (rename the disabled overlay)
mv configuration/traefik/dynamic-identity.yml.disabled \
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

### Identity Provider

- Primary: [Authentik](https://goauthentik.io/)
- Why: Modern self-hosted OIDC/SAML identity provider with flexible authentication flows that fits NetBox RBAC and reverse-proxy fronted deployments.
- Alternatives: Keycloak for mature enterprise federation, ZITADEL for cloud-native and passwordless-first deployments, Authelia when forward-auth MFA is enough and a full IdP is not required
- Integration: Deploy externally and map directory or group claims into NetBox RBAC after first-run bootstrap access is rotated.
### Password Service

- Primary: [Vaultwarden](https://github.com/dani-garcia/vaultwarden)
- Why: Lightweight Bitwarden-compatible password vault for operator, service, and bootstrap secret management.
- Alternatives: Passbolt for browser-centric team password sharing
- Integration: Store NetBox bootstrap, database, Diode, and import credentials there after initial secret-file generation.
### Link Service

- Primary: [Linkding](https://github.com/sissbruecker/linkding)
- Why: Simple self-hosted bookmark catalog for runbooks, vendor documentation, and environment-specific NetBox references.
- Alternatives: Shlink when internal short URLs and click analytics are needed
- Integration: Publish operator URLs, change records, and site-specific NetBox entry points behind the same reverse proxy.
### Cloud Service

- Primary: [Nextcloud](https://nextcloud.com/)
- Why: Self-hosted collaboration hub for files, notes, calendars, and operator attachments that commonly accompany infrastructure data.
- Alternatives: Seafile when fast file sync matters more than broader groupware
- Integration: Keep large documents, diagrams, and evidence external to NetBox while linking back to NetBox objects and exports.

## Privacy Controls

- Bootstrap username: bootstrap-f76ada8f17
- Bootstrap email: bootstrap-f76ada8f17@invalid.local
- Rotation required: True
- Rationale: Use a pseudonymous bootstrap superuser that is not tied to a human identity, store the credentials only in separate local secret files, and disable or rotate the account after creating named RBAC-backed operators.

## First Start

### 1. Populate secrets

Generate real secret values from the examples:

```bash
cd secrets
openssl rand -hex 32 > api_token_pepper_1
openssl rand -base64 24 | tr -d '\n' > db_password
openssl rand -hex 32 > secret_key
openssl rand -base64 24 | tr -d '\n' > superuser_api_token
cp superuser_name.example superuser_name
openssl rand -base64 18 | tr -d '\n' > superuser_password
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
This typically takes 2–5 minutes. Monitor progress with:

```bash
docker compose ps
docker logs netbox-prod-netbox-1 --tail 20
```

Once NetBox shows `(healthy)`, all dependent containers start automatically. If any
remain in `Created` state, re-run `docker compose up -d`.

The `diode-credential-setup` service runs automatically after the superuser sync and
creates the `diode` admin user required by the Diode plugin. This is idempotent and
runs on every stack start.

### 4. Access NetBox

NetBox is available at **https://localhost** (port 443, self-signed TLS certificate).

- **Username**: `bootstrap-f76ada8f17`
- **Password**: the value in `secrets/superuser_password`

The bootstrap account is intended only for first login and RBAC setup — rotate or
disable it after creating named operator accounts.

### 5. Import device-type library (optional)

```bash
docker compose --profile device-type-library-import run --rm device-type-library-import
```

The one-shot importer downloads the pinned `devicetype-library` archive, parses YAML
definitions, and creates objects through `/api/dcim/` REST endpoints. The import is
idempotent — existing objects are skipped.

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

- The Proxmox plugin (netbox-proxbox) is enabled in this bundle using version 0.0.10 which explicitly targets NetBox 4.5.x. Validate in staging before production. For event-driven Proxmox automation without a plugin, the NetBox Labs netbox-proxmox-automation project (https://github.com/netboxlabs/netbox-proxmox-automation) provides a webhook-based alternative.
- The ACL plugin (netbox-acls) version 2.0.0 is enabled and explicitly targets NetBox 4.5.x in the upstream compatibility matrix.
- The Prometheus discovery plugin (netbox-prometheus-sd) is included but disabled because version 0.5 still imports the legacy extras.plugins API and fails on NetBox 4.5.x.

## Notes

- Deployment follows the official netbox-docker plugin workflow baseline pinned to release 4.0.2.
- Track 'alpine' is tied to Alpine Linux 3.23.3 for OS lifecycle alignment.
- Topology, BGP, and DNS plugins are enabled because they have current NetBox 4.5 compatibility evidence from official NetBox Community sources. The DNS plugin (netbox-plugin-dns 1.5.5) explicitly declares min_version='4.5.0'.
- The Diode plugin (netboxlabs-diode-netbox-plugin 1.9.0) is enabled by default and paired with generated diode-auth, diode-ingester, and diode-reconciler services so plugin and reconciler endpoints resolve in the composed deployment.
- netbox-prometheus-sd 0.5 remains disabled by default until its compatibility requirements are satisfied for this generated bundle. netbox-acls 2.0.0 and netbox-proxbox 0.0.10 are now enabled with confirmed NetBox 4.5.x compatibility.
- Requested plugins netbox-config-diff 2.14.2, netbox-floorplan-plugin 0.9.1, and netbox-inventory 2.5.1 are integrated by default using upstream compatibility metadata.
- netbox-reorder-rack 1.1.4 is enabled as a community integration; validate in staging before production because upstream metadata does not publish a strict NetBox 4.5 compatibility matrix.
- Worker-container orchestration is generated explicitly so RQ workers can scale as independent containers while preserving a deterministic startup dependency on NetBox health.
- ORB is generated as an optional discovery profile using the official netboxlabs/orb-agent image and an agent.yaml config, with host networking, a default @every 60m scan cadence, RFC1918 targets, and diode client credential placeholders in configuration/orb/agent.yaml.
- DNS management is provided by netbox-plugin-dns 1.5.5, which explicitly targets NetBox 4.5.0+ and handles zones, records, nameservers, and DNSSEC key templates natively inside NetBox.
- The Proxmox plugin (netbox-proxbox) version 0.0.10 is enabled with confirmed NetBox 4.5.x compatibility. For event-driven Proxmox automation without a plugin, see the NetBox Labs netbox-proxmox-automation project.
- The NetBox community device-type library is pinned by commit and imported through NetBox core bulk-import views rather than an external helper script.
- The bootstrap superuser is pseudonymous and intended only for initial RBAC setup and rotation.
- Least privilege is enforced with dropped Linux capabilities and separated database/bootstrap secret files; the default importer workflow can be overridden to use a dedicated NetBox user.
- A full monitoring stack (Grafana, Prometheus, Loki, Alloy, syslog-ng, node_exporter, snmp_exporter, cAdvisor) is generated as an optional 'monitoring' Compose profile based on enter-the-metrics. Prometheus scrapes the NetBox data plane and monitoring services; Grafana dashboards are provisioned from the pinned upstream repository.
- The netbox-geo-foss companion service integrates open-source geographic data (GeoNames, Natural Earth, OpenStreetMap) into NetBox via the REST API. It runs as a profiled one-shot service after the device-type-library import and requires a GeoNames username and the bootstrap API token.
- The generated plan now includes adjacent FOSS service recommendations for identity, password, link, and cloud workflows; deploy them beside the core stack rather than inside the generated NetBox Compose bundle.
- An identity profile is generated with Authentik (SSO/OIDC identity provider) and Ory Hydra (OAuth2 server for Diode client-credentials). Both are deployed under the 'identity' Compose profile with dedicated Postgres instances and an isolated identity network segment (172.30.0.160/27). Start with: docker compose --profile identity up -d
