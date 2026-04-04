# Feature Alignment

## Topology

The repository enables `netbox-topology-views` because topology visualization is a direct modeling extension and the plugin documents NetBox 4.5 compatibility. The generated configuration enables coordinate persistence and creates the expected static image directory in the custom image.

## BGP

The repository enables `netbox-bgp` because it directly extends NetBox as a source of truth for BGP sessions, peer groups, policy, and AS-path artifacts. The generated configuration exposes the BGP data on a device tab and enables a top-level menu.

## DNS

The repository enables `netbox-plugin-dns` (module: `netbox_dns`) version 1.5.3, which explicitly declares `min_version = "4.5.0"` and is published from the official netbox-community source path. This plugin provides DNS zone, record, nameserver, and DNSSEC key template management natively inside NetBox, making DNS a first-class member of the network source of truth alongside IPAM and topology data.

The generated plugin configuration uses the package defaults. Operators who require custom SOA timers, zone TTL defaults, or filtered RR types can extend `PLUGINS_CONFIG["netbox_dns"]` in the generated `configuration/plugins.py`.

## Proxmox

The repository includes `netbox-proxbox` (module: `netbox_proxbox`) version 0.0.6b2 in the plugin spec list as a documented integration option, but sets it to `enabled=False` because the current release declares `max_version='4.2.99'`, which is incompatible with the pinned NetBox 4.5.x image. Enabling it on a NetBox 4.5 deployment would cause NetBox to refuse startup due to the declared version ceiling.

Two integration paths are available until a NetBox 4.5-compatible netbox-proxbox release ships:

1. **netbox-proxbox (plugin)**: Set `enabled=True` in `DEFAULT_PLUGIN_SPECS` once an officially supported release targeting NetBox 4.5 is available. The plugin provides inventory synchronization (clusters, nodes, VMs, containers, interfaces) from Proxmox VE into NetBox via a FastAPI backend.

2. **NetBox Labs event-driven automation (webhook-based)**: The `netboxlabs/netbox-proxmox-automation` project provides event-driven Proxmox VM provisioning and management triggered by NetBox event rules and webhooks. This approach does not require a NetBox plugin and is compatible with current NetBox 4.x releases. See [https://github.com/netboxlabs/netbox-proxmox-automation](https://github.com/netboxlabs/netbox-proxmox-automation) for setup instructions.

## Requested Plugin Integrations

The generator enables the following user-requested plugins in `DEFAULT_PLUGIN_SPECS`:

- `netbox-config-diff` (`netbox_config_diff`) from `miaow2/netbox-config-diff`
- `netbox-floorplan-plugin` (`netbox_floorplan`) from `netbox-community/netbox-floorplan-plugin`
- `netbox-inventory` (`netbox_inventory`) from `ArnesSI/netbox-inventory`

Compatibility evidence used from upstream metadata:

- `netbox-config-diff` 2.14.0 (`min_version='4.5.0'`, `max_version='4.5.99'`)
- `netbox-floorplan-plugin` 0.9.0 (`min_version='4.5.0-beta1'`, `max_version='4.5.99'`)
- `netbox-inventory` 2.5.0 (`min_version='4.5.0'`)

## ORB Orchestration

The generated bundle includes an ORB discovery profile using the official NetBox Labs Orb agent image:

- Compose service: `orb-agent`
- Env file: `env/orb.env`
- Config: `configuration/orb/agent.yaml`
- Image: `netboxlabs/orb-agent:2.7.0`

This wiring follows upstream Orb docs that require `run -c /opt/orb/agent.yaml` and elevated networking for active discovery. The service is profile-gated (`orb-discovery`) and uses host networking plus `NET_RAW`/`NET_ADMIN` capabilities. Diode client credentials are emitted as explicit placeholders in `configuration/orb/agent.yaml` because orb-agent does not perform environment-variable interpolation in that file. The generated default policy targets RFC1918 ranges, uses `schedule: "@every 60m"` to reduce default scan churn, and starts with `dry_run: true` for safer first boot behavior.

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

The superuser-sync service writes the full v2 token (`nbt_<key>.<plaintext>`) to a shared `token-store` volume so sidecar services (geo-foss) that depend on `netbox-superuser-sync` completion can read the assembled token without needing direct secret file access or knowledge of the v2 token format.

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
- Depends on: `netbox-superuser-sync` (must complete first to write v2 token)
- Env file: `env/geo-foss.env` (requires `GEONAMES_USERNAME` to be set by the operator)
- Authenticates using the full v2 API token (`nbt_<key>.<plaintext>`) read from the `token-store` volume, with fallback to the raw secret file
- Persists downloaded geographic data in a `geo-foss-cache` volume to avoid re-downloading across runs
- Runs with dropped capabilities and `no-new-privileges`

## Traefik Reverse Proxy

The generated bundle places a Traefik v3.2 reverse proxy at the edge of the deployment:

- Listens on port 443 with TLS termination using a self-signed certificate (auto-generated by the `traefik-certgen` init container on first start).
- Routes all HTTPS traffic to the WAF sidecar via the dynamic configuration in `configuration/traefik/dynamic.yml`.
- Enables gzip compression middleware for responses.
- The API dashboard is disabled; only the `/ping` healthcheck endpoint is active.
- Traefik is the only service with a published host port.

The self-signed certificate includes SAN entries for `localhost`, `traefik`, `netbox`, `127.0.0.1`, and the host's hostname (if it passes validation). To use CA-signed certificates, replace the files in the `traefik-certs` volume.

## WAF Sidecar

An OWASP ModSecurity Core Rule Set (CRS) WAF runs as an nginx-based sidecar between Traefik and NetBox:

- Image: `owasp/modsecurity-crs:nginx`
- Listens on port 8081 (internal only)
- Proxies validated requests to `http://netbox:8080`
- Sets `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-Port` headers so NetBox sees the correct external origin
- Connected to both the `app` and `data` networks

## Scoped Docker Networks

The generated compose file defines five isolated bridge networks with explicit CIDR allocations:

| Network      | Purpose                                                   | Deterministic CIDR    |
|--------------|-----------------------------------------------------------|-----------------------|
| `edge`       | Traefik ↔ WAF                                            | `172.30.0.0/27`       |
| `app`        | WAF ↔ NetBox                                              | `172.30.0.32/27`      |
| `data`       | NetBox, Postgres, Valkey, Diode, workers, imports         | `172.30.0.64/27`      |
| `security`   | Wazuh agent                                               | `172.30.0.96/28`      |
| `monitoring` | Grafana, Prometheus, Loki, Promtail, syslog-ng, exporters | `172.30.0.128/27`     |

In `deterministic` CIDR mode (default), each segment uses a fixed `/27` or `/28` block from `172.30.0.0/24`. In `dynamic` mode, segments are allocated from `172.31.0.0/16` with prefix lengths sized to the required host count.

Services are placed on the minimum set of networks needed:
- Traefik: `edge` + `app`
- WAF: `app` + `data`
- NetBox, workers, Postgres, Valkey, Diode, imports: `data`
- ORB: host networking mode (`network_mode: host`)
- Wazuh agent: `security`
- Monitoring services: `monitoring` (Prometheus also joins `data` for scraping)

## Valkey

Valkey replaces Redis as the cache and task-queue backend. The generated compose uses a pinned Valkey image (per lifecycle track) with append-only persistence. NetBox env files reference `valkey` as both `REDIS_CACHE_HOST` and `REDIS_HOST`.

## Diode Auth

Diode is deployed as three companion services in the `data` network:

- `diode-auth` (`netboxlabs/diode-auth:1.12.0`)
- `diode-ingester` (`netboxlabs/diode-ingester:1.13.0`)
- `diode-reconciler` (`netboxlabs/diode-reconciler:1.13.0`)

The generated bundle includes `env/diode.env` with runtime values used by `diode-auth`, `diode-ingester`, and `diode-reconciler`, including Redis/Postgres/Diode client settings required by shellless container images.

Plugin configuration keeps `diode_target_override` pointed at `grpc://diode-auth:8080/diode` and sets `netbox_to_diode_client_secret_name` to `netbox_to_diode`, aligning with the upstream plugin's default secret lookup model.

## CI/CD Localization

The repository localizes CI/CD into Docker. Local validation and GitHub Actions both use `docker compose -f docker-compose.ci.yml` so linting, type checking, tests, and sample bundle generation run inside the repository's CI image rather than relying on host Python tooling. Bundle artifacts are written back into the workspace under `.artifacts/` so the same containerized flow works locally and in CI.

## Monitoring Stack (enter-the-metrics)

The generated bundle includes a complete monitoring stack based on [enter-the-metrics](https://github.com/nullroute-commits/enter-the-metrics), available as an optional `monitoring` Compose profile. The upstream repository (BSD-licensed) provides a Docker Compose-based metrics and log collection stack; the deployment factory adapts its service definitions, configuration files, and Grafana provisioning into the generated bundle.

### Included Services

| Service | Image | Purpose |
|---|---|---|
| Grafana | `grafana/grafana:11.4.0` | Dashboard visualization with Prometheus and Loki datasources |
| Prometheus | `prom/prometheus:v2.54.1` | Metrics collection and storage |
| Loki | `grafana/loki:3.2.1` | Log aggregation |
| Promtail | `grafana/promtail:3.2.1` | Log shipping agent (syslog → Loki) |
| syslog-ng | `balabit/syslog-ng:4.11.0` | Syslog forwarding to Promtail |
| node-exporter | `prom/node-exporter:v1.8.2` | Host system metrics |
| snmp-exporter | `prom/snmp-exporter:v0.27.0` | SNMP device metrics |
| cAdvisor | `gcr.io/cadvisor/cadvisor:v0.51.0` | Docker container metrics |

### Network Placement

All monitoring services are placed on the `monitoring` network. Prometheus also joins the `data` network so it can scrape metrics from NetBox stack services (NetBox, Postgres, Valkey, Diode, workers). This follows the least-privilege principle: monitoring services cannot reach the edge or app networks.

### Configuration Adaptation

The upstream configuration files are adapted to the generated deployment:

- **Prometheus**: Scrape targets reference Compose service names (e.g., `prometheus:9090`, `grafana:3000`, `cadvisor:8080`). Operators can add custom scrape targets for their own node-exporters and SNMP devices.
- **Loki**: Filesystem-backed storage with embedded cache, analytics reporting disabled.
- **Promtail**: Listens for syslog on port 1514 (TCP) with relabeling for hostname, source IP, and destination IP.
- **syslog-ng**: Forwards all syslog sources (local + network) to Promtail via TCP 1514.
- **Grafana**: Provisioned with Prometheus and Loki datasources and a dashboard provider pointing to the `performance_overview` directory.

### Dashboard Provisioning

The upstream repository includes five preconfigured Grafana dashboards (Docker, Grafana, Loki, Prometheus, Node Exporter). These are large JSON files that are not embedded in the generator. Instead, a `scripts/fetch-monitoring-dashboards.sh` script is generated that downloads the dashboards from the pinned upstream repository commit (`abb9825`). The dashboards are placed in a shared Docker volume mounted by Grafana.

### Why Profile-Gated

The monitoring stack is optional because:
1. Not all deployments need local monitoring (some organizations use centralized monitoring).
2. cAdvisor and node-exporter require privileged access or host volume mounts.
3. The monitoring services add significant resource overhead on small hosts.

Operators enable the monitoring profile when they want self-contained observability alongside NetBox.

### Source and License

- Repository: https://github.com/nullroute-commits/enter-the-metrics
- Pinned ref: `abb9825`
- License: BSD (compatible with MIT)
