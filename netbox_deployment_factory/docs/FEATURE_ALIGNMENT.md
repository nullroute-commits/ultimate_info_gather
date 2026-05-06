# Feature Alignment

## Topology

The repository enables `netbox-topology-views` because topology visualization is a direct modeling extension and the plugin documents NetBox 4.5 compatibility. The generated configuration enables coordinate persistence and creates the expected static image directory in the custom image.

## BGP

The repository enables `netbox-bgp` because it directly extends NetBox as a source of truth for BGP sessions, peer groups, policy, and AS-path artifacts. The generated configuration exposes the BGP data on a device tab and enables a top-level menu.

## DNS

The repository enables `netbox-plugin-dns` (module: `netbox_dns`) version 1.5.5, which explicitly declares `min_version = "4.5.0"` and is published from the official netbox-community source path. This plugin provides DNS zone, record, nameserver, and DNSSEC key template management natively inside NetBox, making DNS a first-class member of the network source of truth alongside IPAM and topology data.

The generated plugin configuration uses the package defaults. Operators who require custom SOA timers, zone TTL defaults, or filtered RR types can extend `PLUGINS_CONFIG["netbox_dns"]` in the generated `configuration/plugins.py`.

## Proxmox

The repository includes `netbox-proxbox` (module: `netbox_proxbox`) version 0.0.10 in the plugin spec list with `enabled=True` because this release explicitly lists NetBox 4.5.x in its requirements.

The plugin provides inventory synchronization (clusters, nodes, VMs, containers, interfaces) from Proxmox VE into NetBox via a FastAPI backend. For event-driven Proxmox automation without a plugin, the `netboxlabs/netbox-proxmox-automation` project provides webhook-based VM provisioning and management.

## ACLs

The repository includes `netbox-acls` (`netbox_acls`) version 2.0.0 in the plugin spec list with `enabled=True` because the upstream compatibility matrix explicitly targets NetBox 4.5.x for this version.

**Configuration:** `top_level_menu: True`.

## Prometheus Service Discovery

The repository includes `netbox-prometheus-sd` (`netbox_prometheus_sd`) version 0.5 in the plugin spec list but sets it to `enabled=False` because the current release imports the legacy `extras.plugins` API and fails to load on NetBox 4.5.x. The plugin provides Prometheus HTTP SD endpoints for NetBox devices. Enable once an updated release targets modern NetBox plugin APIs.

**Configuration:** `custom_field_name: "monitored"`, `target_port: 9100`, `gnmic_target_port: 32767`.

## Reorder Rack

The repository enables `netbox-reorder-rack` (`netbox_reorder_rack`) version 1.1.4. This community plugin exposes drag-and-drop rack reordering. The upstream compatibility matrix states `>=4.0.0`. Validate in staging before production because upstream metadata does not publish a strict NetBox 4.5 compatibility matrix.

**Configuration:** Uses package defaults.

## Requested Plugin Integrations

The generator enables the following user-requested plugins in `DEFAULT_PLUGIN_SPECS`:

- `netbox-config-diff` (`netbox_config_diff`) from `miaow2/netbox-config-diff`
- `netbox-floorplan-plugin` (`netbox_floorplan`) from `netbox-community/netbox-floorplan-plugin`
- `netbox-inventory` (`netbox_inventory`) from `ArnesSI/netbox-inventory`

Compatibility evidence used from upstream metadata:

- `netbox-config-diff` 2.14.2 (`min_version='4.5.0'`, `max_version='4.5.99'`)
- `netbox-floorplan-plugin` 0.9.1 (`min_version='4.5.0-beta1'`, `max_version='4.5.99'`)
- `netbox-inventory` 2.5.1 (`min_version='4.5.0'`)

### Config Diff

The repository includes `netbox-config-diff` (`netbox_config_diff`) version 2.14.2 in the plugin spec list but sets it to `enabled=False`. This community plugin provides configuration drift detection and compliance reporting for network devices. It is disabled because version 2.14.2 raises `strawberry.exceptions.duplicated_type_name.DuplicatedTypeName: Type StrFilterLookup is defined multiple times in the schema` on NetBox 4.5.7 due to a Strawberry GraphQL schema registration conflict. Enable once an upstream release resolves the conflict.

### Floorplan

The repository enables `netbox-floorplan-plugin` (`netbox_floorplan`) version 0.9.1. This community plugin provides visual floorplan management for sites and locations within NetBox.

**Configuration:** Uses package defaults.

### Inventory

The repository enables `netbox-inventory` (`netbox_inventory`) version 2.5.1. This community plugin extends NetBox with asset lifecycle tracking, purchase, and warranty management for hardware inventory.

**Configuration:** Uses package defaults.

## Diode Plugin

The repository enables `netboxlabs-diode-netbox-plugin` (`netbox_diode_plugin`) version 1.9.0. This is the official NetBox Labs Diode plugin that provides reconciliation APIs for automated network state ingestion. Upstream compatibility table shows NetBox >= 4.5.0 support.

**Configuration:** `diode_username: "diode"`, `diode_target_override: "grpc://diode-proxy:80"`, `secrets_path: "/run/secrets/"`, `netbox_to_diode_client_id: "netbox-to-diode"`, `netbox_to_diode_client_secret_name: "netbox_to_diode"`. The `diode_target_override` points at the generated `diode-proxy` Compose service (nginx mux on port 18084 inside the container network) so plugin traffic reaches the gRPC ingester through the proxy.

The generated bundle includes three companion Diode services in the `data` network: `diode-auth` (`netboxlabs/diode-auth:1.12.0`), `diode-ingester` (`netboxlabs/diode-ingester:1.13.0`), and `diode-reconciler` (`netboxlabs/diode-reconciler:1.13.0`). Diode credential provisioning (`scripts/setup-diode-credential.sh`) is called automatically by the `netbox-init` single-init container (see [NetBox Bootstrap Init](#netbox-bootstrap-init) below).

## NetBox Bootstrap Init

The generated bundle consolidates all NetBox bootstrap logic into a single `netbox-init` one-shot service, replacing the former two-container chain (`netbox-superuser-sync` → `diode-credential-setup`).

| Step | Script | What it does |
|------|--------|--------------|
| 1/2 | `scripts/sync-superuser.sh` | Creates the pseudonymous bootstrap superuser, mints a v2 API token, and writes the full token to the `token-store` volume |
| 2/2 | `scripts/setup-diode-credential.sh` | Creates the Diode admin user and API token in NetBox for the Diode plugin credential handshake |

The controlling entrypoint, `scripts/netbox-init.sh`, calls both scripts in sequence using their stable individual paths so each script remains independently callable by operators.

**Compose topology:**
```
netbox (healthy) → netbox-init → [geo-foss-import, device-type-library-import]
```

**Why one container?** Both steps use the same NetBox image and Django runtime. Merging them eliminates one `service_completed_successfully` dependency hop and gives every downstream service a single, unambiguous gate to wait on, reducing startup race surface.

**Secrets (union of both former services):**
`db_password`, `api_token_pepper_1`, `secret_key`, `netbox_to_diode`, `superuser_name`, `superuser_password`, `superuser_api_token`

## ORB Orchestration

The generated bundle includes an ORB discovery profile using the official NetBox Labs Orb agent image:

- Compose service: `orb-agent`
- Env file: `env/orb.env`
- Config: `configuration/orb/agent.yaml`
- Image: `netboxlabs/orb-agent:2.7.0`

This wiring follows upstream Orb docs that require `run -c /opt/orb/agent.yaml` and elevated networking for active discovery. The service is profile-gated (`orb-discovery`) and uses host networking plus `NET_RAW`/`NET_ADMIN` capabilities. The generated default policy targets RFC1918 ranges, uses `schedule: "@every 120m"` to reduce default scan churn, and starts with `dry_run: true` for safer first boot behavior.

### Automated Secret Injection (orb-bootstrap)

The `client_secret` field in `agent.yaml` cannot use Docker-secrets `_FILE` conventions because the ORB agent reads `agent.yaml` as a plain YAML file without environment-variable interpolation. Previously this required running `scripts/populate-env-secrets.sh` before first start.

The generated bundle now includes an `orb-bootstrap` init container that automates this step:

1. `orb-bootstrap` starts before `orb-agent` (Compose dependency: `service_completed_successfully`)
2. It depends on `hydra-bootstrap-clients` completing so the Diode OAuth2 client is registered first
3. It reads `secrets/diode_client_id` and `secrets/diode_client_secret` via Docker secret mounts
4. It copies the template `configuration/orb/agent.yaml` into the `orb-config` Docker volume
5. It patches `client_id: replace-client-id` and `client_secret: replace-me` with the real values using `sed`
6. `orb-agent` reads the patched config from the `orb-config` volume (mounted read-only)

The `scripts/orb-bootstrap.sh` script performs the credential injection. `scripts/populate-env-secrets.sh` no longer modifies `agent.yaml` — it only handles `env/diode.env`.

### Startup Order

```
hydra-bootstrap-clients → orb-bootstrap → orb-agent
diode-auth (started) ─────────────────→ orb-agent
```

### Enabling Live Scanning

The generated `configuration/orb/agent.yaml` defaults to `dry_run: false` — active RFC1918 scanning is enabled from first boot. To restrict to passive observation, set `dry_run: true` before starting the ORB profile:

1. Edit `configuration/orb/agent.yaml` and set `dry_run: true`
2. Start the ORB profile:
   ```bash
   docker compose --profile orb-discovery up -d
   ```

Diode client credentials (`client_id` and `client_secret`) are emitted as `replace-client-id` / `replace-me` placeholders in the template `configuration/orb/agent.yaml` because orb-agent does not perform environment-variable interpolation. The `orb-bootstrap` container injects both values automatically at startup using Docker secrets.

## Adjacent FOSS Services

The deployment generator now records recommended adjacent services in the generated README and `deployment-plan.json` so operators can standardize the rest of the platform stack without bloating the core NetBox bundle:

- **Identity provider**: Authentik preferred; Keycloak, ZITADEL, and Authelia called out as fit-specific alternatives.
- **Password service**: Vaultwarden preferred; Passbolt as a collaborative alternative.
- **Link service**: Linkding preferred; Shlink as the short-link alternative.
- **Cloud service**: Nextcloud preferred; Seafile as the performance-oriented file-sync alternative.

These are intentionally guidance-only integrations. The generator keeps them outside the bundled Compose stack and instead recommends deploying them beside NetBox behind the same reverse proxy and access-control model.

## Device-Type Library

The repository includes the NetBox community device-type library as a pinned external content source rather than an in-application plugin. The generated deployment bundle uses the **NetBox REST API** to create manufacturers, device types (with full component templates), module types, and rack types. The import runs as a dedicated one-shot Compose profile service (`device-type-library-import`) with dropped capabilities and `no-new-privileges`, downloads the library archive into temporary storage, parses YAML definitions, and creates objects through `/api/dcim/` endpoints with v2 Bearer token authentication.

Key features of the REST API importer:
- **Component templates**: Creates interface, console-port, power-port, power-outlet, rear-port, front-port, device-bay, module-bay, and inventory-item templates for each device/module type.
- **Idempotent**: Existing objects are looked up by slug (or model+manufacturer for module types) and skipped. Re-running the import produces no duplicates.
- **Vendor filtering**: Set `DEVICE_TYPE_LIBRARY_VENDORS` to a comma-separated list of vendor directory names (e.g., `cisco,juniper`) to import only specific vendors.
- **Bulk creation**: Component templates are POSTed in batches for efficiency.

## API Tokens

The repository generates an `api_token_pepper_1` secret alongside the bootstrap secrets so NetBox can mint and validate v2 API tokens. The superuser sync script creates a v2 token from the `superuser_api_token` secret file using Token.validate() for idempotent re-runs. The device-type importer authenticates with `Authorization: Bearer nbt_<key>.<plaintext>` format, where the key (HMAC digest) is read from the Token ORM and the plaintext comes from the mounted secret file.

The `netbox-init` service writes the full v2 token (`nbt_<key>.<plaintext>`) to a shared `token-store` volume so sidecar services (geo-foss) that depend on `netbox-init` completion can read the assembled token without needing direct secret file access or knowledge of the v2 token format.

## Geographic Data (netbox-geo-foss)

The repository includes the `netbox-geo-foss` sidecar as a profiled one-shot Compose service (`netbox-geo-foss`) that imports geographic data into NetBox as a three-tier Region hierarchy (continent → country → city) using pynetbox. This is a standalone Python application, not a NetBox plugin; it connects to a running NetBox instance externally.

The import creates:
- **7 continent regions** as top-level Regions (Africa, Asia, Europe, North America, South America, Oceania, Antarctica)
- **~64 country regions** as children of their continent
- **~215 city regions** as children of their country (cities with population ≥ 15,000)

Country and city data is fetched from the GeoNames REST API when available. When the GeoNames API is unavailable or rate-limited, the import falls back to an embedded dataset of 64 countries and ~215 major cities covering all continents.

Key integration details:

- Image: built locally via `Dockerfile-GeoFoss` (clones pinned commit from upstream)
- Repository: `https://github.com/nullroute-commits/netbox-geo-foss.git` pinned at `50c3c16`
- Import script: `scripts/import-geo-data.py` (pynetbox-based, replaces upstream placeholder CLI)
- Compose profile: `geo-foss-import`
- Depends on: `netbox-init` (must complete first to write v2 token)
- Env file: `env/geo-foss.env` (requires `GEONAMES_USERNAME` to be set by the operator)
- Authenticates using the full v2 API token (`nbt_<key>.<plaintext>`) read from the `token-store` volume, with fallback to the raw secret file
- Persists downloaded geographic data in a `geo-foss-cache` volume to avoid re-downloading across runs
- Runs with dropped capabilities and `no-new-privileges`

## TLS Termination

The generated bundle supports two TLS termination modes for the Traefik reverse proxy:

### Self-Signed (default)

When no `--fqdn` is provided, the factory generates a `traefik-certgen` init container and `scripts/generate-traefik-cert.sh` that creates a self-signed certificate with SAN entries for the host IP, `localhost`, and internal service names. The certificate is stored in a `traefik-certs` Docker volume and referenced statically in `configuration/traefik/dynamic.yml`. This mode requires no external dependencies and is suitable for development, lab, and air-gapped environments.

### Let's Encrypt ACME (DNS-01 Cloudflare)

When the factory is invoked with `--fqdn <domain>` and `--acme-email <email>`, the generated bundle switches to automated certificate management via Let's Encrypt:

- The `traefik-certgen` init container and self-signed cert script are omitted.
- Traefik is configured with ACME DNS-01 challenge using the Cloudflare provider (`CF_DNS_API_TOKEN_FILE` from a Docker secret).
- Port 80 is published with an automatic HTTP→HTTPS redirect.
- An `acme-data` volume persists the ACME account key and certificates.
- `configuration/traefik/dynamic.yml` uses `certResolver: letsencrypt` on routers with the FQDN as the main domain, replacing static certificate references.
- `env/netbox.env` includes the FQDN in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.
- `secrets/cf_dns_api_token.example` is generated instead of the cert generation script.

This mode is appropriate for production deployments where a trusted TLS certificate is required. The operator must provide a Cloudflare API token with `Zone:DNS:Edit` permission for the zone containing the FQDN.

The TLS mode is determined at plan time by `_derive_tls_profile()` in the planner and stored as a `TlsProfile` dataclass on the `DeploymentPlan`. The renderer conditionally emits the appropriate Compose services, Traefik configuration, environment variables, scripts, and secrets based on `plan.tls.mode`.

## Traefik Reverse Proxy

The generated bundle places a Traefik v3.6 reverse proxy at the edge of the deployment:

- Listens on port 443 with TLS termination using a self-signed certificate (auto-generated by the `traefik-certgen` init container on first start).
- Routes all HTTPS traffic to the WAF sidecar via the dynamic configuration in `configuration/traefik/dynamic.yml`.
- Enables gzip compression middleware for responses.
- The API dashboard is disabled; only the `/ping` healthcheck endpoint is active.
- Traefik is the only service with a published host port.

The self-signed certificate includes SAN entries for `localhost`, `traefik`, `netbox`, `127.0.0.1`, and the host's hostname (if it passes validation). To use CA-signed certificates, replace the files in the `traefik-certs` volume.

## WAF Sidecar

An OWASP ModSecurity Core Rule Set (CRS) WAF runs as an nginx-based sidecar between Traefik and NetBox:

- Image: `owasp/modsecurity-crs:4.25.0-nginx-lts`
- Listens on port 8081 (internal only)
- Proxies validated requests to `http://netbox:8080`
- Sets `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-Port` headers so NetBox sees the correct external origin
- Connected to both the `app` and `data` networks

## Scoped Docker Networks

The generated compose file defines six isolated bridge networks with explicit CIDR allocations:

| Network      | Purpose                                                   | Deterministic CIDR    |
|--------------|-----------------------------------------------------------|-----------------------|
| `edge`       | Traefik ↔ WAF                                            | `172.30.0.0/27`       |
| `app`        | WAF ↔ NetBox                                              | `172.30.0.32/27`      |
| `data`       | NetBox, Postgres, Valkey, Diode, workers, imports         | `172.30.0.64/27`      |
| `security`   | Wazuh agent                                               | `172.30.0.96/28`      |
| `monitoring` | Grafana, Prometheus, Loki, Alloy, cAdvisor                             | `172.30.0.128/27`     |
| `identity`   | Authentik, Ory Hydra, dedicated Postgres instances        | `172.30.0.160/27`     |

In `deterministic` CIDR mode (default), each segment uses a fixed `/27` or `/28` block from `172.30.0.0/24`. In `dynamic` mode, segments are allocated from `172.31.0.0/16` with prefix lengths sized to the required host count.

Services are placed on the minimum set of networks needed:
- Traefik: `edge` + `app` (Authentik forward-auth remains reachable through the `app` network)
- WAF: `app` + `data`
- NetBox, workers, Postgres, Valkey, Diode, imports: `data`
- ORB: host networking mode (`network_mode: host`)
- Wazuh agent: host networking mode (`network_mode: host`)
- Monitoring services: Grafana, Prometheus, Loki, Alloy, cAdvisor: `monitoring` (Prometheus also joins `data` for scraping); syslog-ng, node-exporter, snmp-exporter: host networking mode (`network_mode: host`)
- Authentik, Hydra, and their Postgres instances: `identity` (Diode services on `data` connect to Hydra through `identity`)

## Valkey

Valkey replaces Redis as the cache and task-queue backend. The generated compose uses a pinned Valkey image (per lifecycle track) with append-only persistence. NetBox env files reference `valkey` as both `REDIS_CACHE_HOST` and `REDIS_HOST`.

## Diode Auth

Diode is deployed as three companion services in the `data` network:

- `diode-auth` (`netboxlabs/diode-auth:1.12.0`)
- `diode-ingester` (`netboxlabs/diode-ingester:1.13.0`)
- `diode-reconciler` (`netboxlabs/diode-reconciler:1.13.0`)

The generated bundle includes `env/diode.env` with runtime values used by `diode-auth`, `diode-ingester`, and `diode-reconciler`, including Redis/Postgres/Diode client settings required by shellless container images. Three values are emitted as `replace-me` placeholders: `REDIS_PASSWORD`, `POSTGRES_PASSWORD`, and `DIODE_TO_NETBOX_CLIENT_SECRET`. The operator must replace these with the corresponding Docker secret values (`secrets/diode_redis_password`, `secrets/db_password`, and `secrets/netbox_to_diode` respectively) before starting the stack.

Plugin configuration keeps `diode_target_override` pointed at `grpc://diode-auth:8080/diode` and sets `netbox_to_diode_client_secret_name` to `netbox_to_diode`, aligning with the upstream plugin's default secret lookup model.

## CI/CD Localization

The repository localizes CI/CD into Docker. Local validation and GitHub Actions both use `docker compose -f docker-compose.ci.yml` so linting, type checking, tests, and sample bundle generation run inside the repository's CI image rather than relying on host Python tooling. Bundle artifacts are written back into the workspace under `.artifacts/` so the same containerized flow works locally and in CI.

## Monitoring Stack (enter-the-metrics)

The generated bundle includes a complete monitoring stack based on [enter-the-metrics](https://github.com/nullroute-commits/enter-the-metrics), available as an optional `monitoring` Compose profile. The upstream repository (BSD-licensed) provides a Docker Compose-based metrics and log collection stack; the deployment factory adapts its service definitions, configuration files, and Grafana provisioning into the generated bundle.

### Included Services

| Service | Image | Purpose |
|---|---|---|
| Grafana | `grafana/grafana:12.4.2` | Dashboard visualization with Prometheus and Loki datasources |
| Prometheus | `prom/prometheus:v3.11.0` | Metrics collection and storage |
| Loki | `grafana/loki:3.7.1` | Log aggregation |
| Alloy | `grafana/alloy:v1.15.0` | Log shipping agent (syslog → Loki) |
| syslog-ng | `balabit/syslog-ng:4.11.0` | Syslog forwarding to Alloy |
| node-exporter | `prom/node-exporter:v1.11.1` | Host system metrics |
| snmp-exporter | `prom/snmp-exporter:v0.30.1` | SNMP device metrics |
| cAdvisor | `gcr.io/cadvisor/cadvisor:v0.52.1` | Docker container metrics |

### Network Placement

All monitoring services are placed on the `monitoring` network. Prometheus also joins the `data` network so it can scrape metrics from NetBox stack services (NetBox, Postgres, Valkey, Diode, workers). This follows the least-privilege principle: monitoring services cannot reach the edge or app networks.

### Configuration Adaptation

The upstream configuration files are adapted to the generated deployment:

- **Prometheus**: Scrape targets reference Compose service names (e.g., `prometheus:9090`, `grafana:3000`, `cadvisor:8080`). Operators can add custom scrape targets for their own node-exporters and SNMP devices.
- **Loki**: Filesystem-backed storage with embedded cache, analytics reporting disabled.
- **Alloy**: Listens for syslog on port 5514 (TCP) with relabeling for hostname, source IP, and destination IP.
- **syslog-ng**: Forwards all syslog sources (local + network) to Alloy via TCP 5514. Uses `network_mode: host`, so it targets `127.0.0.1` rather than the `alloy` service name. Port 5514 avoids conflicts with wazuh-remoted (1514) and syslog-ng's own RFC 5425 TLS listener (6514).
- **Grafana**: Provisioned with Prometheus and Loki datasources and a dashboard provider pointing to the `performance_overview` directory.

### Dashboard Provisioning

The upstream repository includes five preconfigured Grafana dashboards (Docker, Grafana, Loki, Prometheus, Node Exporter). These are large JSON files that are not embedded in the generator. Instead, a `scripts/fetch-monitoring-dashboards.sh` script is generated that downloads the dashboards from the pinned upstream repository commit (`706ed92`). The dashboards are placed in a shared Docker volume mounted by Grafana.

### Why Profile-Gated

The monitoring stack is optional because:
1. Not all deployments need local monitoring (some organizations use centralized monitoring).
2. cAdvisor and node-exporter require privileged access or host volume mounts.
3. The monitoring services add significant resource overhead on small hosts.

Operators enable the monitoring profile when they want self-contained observability alongside NetBox.

### Source and License

- Repository: https://github.com/nullroute-commits/enter-the-metrics
- Pinned ref: `706ed92`
- License: BSD (compatible with MIT)

## Identity Services (Authentik profile + core Ory Hydra)

The generated bundle splits identity services between an optional Authentik `identity` profile for SSO and an always-on Hydra core stack for Diode OAuth2 client-credentials grants. These services share the isolated `identity` network segment (`172.30.0.160/27` in deterministic mode).

### Included Services

| Service | Image | Purpose |
|---|---|---|
| `authentik-postgres` | `postgres:18` / `postgres:18-alpine` | Dedicated Postgres for Authentik |
| `authentik-server` | `ghcr.io/goauthentik/server:2026.2.2` | SSO/OIDC identity provider |
| `authentik-worker` | `ghcr.io/goauthentik/server:2026.2.2` | Authentik background worker |
| `authentik-bootstrap-netbox` | `ghcr.io/goauthentik/server:2026.2.2` | Init container: configures NetBox as an OAuth2 application |
| `hydra-postgres` | `postgres:18` / `postgres:18-alpine` | Dedicated Postgres for Ory Hydra |
| `hydra-migrate` | `oryd/hydra:v2.3.0` | Hydra database migration init container |
| `hydra` | `oryd/hydra:v2.3.0` | OAuth2/OIDC server for Diode client-credentials |
| `hydra-bootstrap-clients` | `oryd/hydra:v2.3.0` | Init container: provisions Diode OAuth2 client |

### Remote Authentication Integration

The generated `configuration/extra.py` enables NetBox remote authentication:

- `REMOTE_AUTH_ENABLED = True`
- `REMOTE_AUTH_BACKEND = "netbox.authentication.RemoteUserBackend"`
- `REMOTE_AUTH_HEADER = "HTTP_X_AUTHENTIK_USERNAME"`
- `REMOTE_AUTH_USER_EMAIL = "HTTP_X_AUTHENTIK_EMAIL"`
- `REMOTE_AUTH_AUTO_CREATE_USER = True`

Authentik forwards the authenticated username and email via HTTP headers through the reverse proxy chain (Traefik → WAF → NetBox). Users are auto-created in NetBox on first login.

### Credential Flow

Ory Hydra provides the OAuth2/OIDC server required by `diode-auth` for client-credentials grants. The `hydra-bootstrap-clients` init container provisions the Diode client using `scripts/setup-diode-credential.sh`. The `diode-auth` service on the `data` network connects to Hydra through the `identity` network for OAuth2 token exchange.

### Why the Authentik Profile Is Optional

The Authentik profile is optional because:
1. Not all deployments need self-hosted SSO (some organizations use existing IdPs).
2. Enabling Authentik adds another Postgres-backed application and extra resource overhead.
3. The core NetBox stack still boots with the pseudonymous bootstrap account, while Hydra remains available for Diode.

## Security Observability (Wazuh)

The generated bundle includes a Wazuh security-observability stack gated by the `security-observability` Compose profile.

### Included Services

| Service | Image | Purpose |
|---|---|---|
| `wazuh-manager` | `wazuh/wazuh-manager:4.14.4` | SIEM / XDR manager: collects and correlates security events |
| `wazuh-agent` | `wazuh/wazuh-agent:4.14.4` | Agent installed alongside the stack host; reports to the local manager |

### Network Mode

Both services use `network_mode: host`. This allows wazuh-remoted (TCP 1514) to accept direct agent connections without NAT and lets wazuh-agent reach the manager at `127.0.0.1` on the same network namespace.

### Wazuh Manager Healthcheck

The wazuh-manager healthcheck is designed to survive a WSL2 network initialization race:

```
pgrep -x wazuh-remoted > /dev/null || /var/ossec/bin/wazuh-remoted 2>/dev/null || true;
/var/ossec/bin/wazuh-control status 2>&1 | grep -q 'wazuh-authd is running'
```

On WSL2, wazuh-remoted may fail to bind TCP 1514 at first start with ENOTCONN (errno 107) due to network stack initialization timing. The healthcheck self-heals by attempting to restart wazuh-remoted before checking authd status. With `retries: 20` and `interval: 30s`, the manager becomes healthy within 60–90 seconds on affected systems.

### Agent Registration

`wazuh-agent` sets `WAZUH_MANAGER_SERVER: "127.0.0.1"` (not `WAZUH_MANAGER`) to match the environment variable expected by the official Wazuh agent Docker image. The agent depends on `wazuh-manager: condition: service_healthy` to ensure the manager and authd are ready before the agent attempts registration.

### Persistent Volumes

- `wazuh-manager-data`: Wazuh manager state (rules, decoders, internal DB)
- `wazuh-manager-logs`: Wazuh alert and log files
