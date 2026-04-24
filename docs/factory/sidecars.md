# Sidecar Services

The generated deployment bundle includes several sidecar services that extend NetBox functionality. These services are profile-gated and run as one-shot or background containers.

## Device-Type Library Import

The device-type library import service downloads and imports device types, module types, rack types, and manufacturers from the [NetBox community device-type library](https://github.com/netbox-community/devicetype-library).

### Configuration

| Property | Value |
|----------|-------|
| Compose service | `device-type-library-import` |
| Compose profile | `device-type-library-import` |
| Repository | `https://github.com/netbox-community/devicetype-library.git` |
| Pinned commit | `cf50cfe` |
| Vendor filter env var | `DEVICE_TYPE_LIBRARY_VENDORS` |

### How It Works

1. Downloads the pinned library archive into temporary storage.
2. Parses YAML device-type, module-type, and rack-type definitions.
3. Creates objects through `/api/dcim/` REST endpoints using v2 Bearer token authentication.
4. **Idempotent**: Existing objects are looked up by slug and skipped. Re-running the import produces no duplicates.

### Usage

```bash
# Import all vendors
docker compose --profile device-type-library-import run --rm device-type-library-import

# Import only specific vendors
docker compose --profile device-type-library-import run \
  -e DEVICE_TYPE_LIBRARY_VENDORS=cisco,juniper \
  device-type-library-import
```

### Component Templates

The importer creates full component templates for each device and module type:

- Interface templates
- Console port and server port templates
- Power port and outlet templates
- Rear port and front port templates
- Device bay and module bay templates
- Inventory item templates

### Generated Files

| File | Description |
|------|-------------|
| `scripts/run-device-type-library-import.sh` | Import runner script |
| `scripts/import-device-type-library.py` | REST API import implementation |
| `env/device-type-library-import.env` | Import environment variables |

---

## Geographic Data (netbox-geo-foss)

The geo-foss sidecar imports geographic data into NetBox as a three-tier Region hierarchy (continent → country → city) using pynetbox.

### Configuration

| Property | Value |
|----------|-------|
| Compose service | `netbox-geo-foss` |
| Compose profile | `geo-foss-import` |
| Repository | `https://github.com/nullroute-commits/netbox-geo-foss.git` |
| Pinned commit | `50c3c16` |
| Image | Built locally via `Dockerfile-GeoFoss` |

### What Gets Imported

- **7 continent regions** as top-level Regions (Africa, Asia, Europe, North America, South America, Oceania, Antarctica)
- **~64 country regions** as children of their continent
- **~215 city regions** as children of their country (cities with population ≥ 15,000)

### Data Sources

Country and city data is fetched from the GeoNames REST API when available. When the GeoNames API is unavailable or rate-limited, the import falls back to an embedded dataset of 64 countries and ~215 major cities covering all continents.

### Usage

```bash
# Build the geo-foss image
docker compose build netbox-geo-foss

# Run the import
docker compose --profile geo-foss-import run --rm netbox-geo-foss
```

!!! note "GeoNames Account"
    Set `GEONAMES_USERNAME` in `env/geo-foss.env` to a valid GeoNames account for live API data. Without it, the import uses the embedded dataset.

### Dependencies

- Depends on `netbox-superuser-sync` having completed (so the v2 API token is available in the `token-store` volume).
- Authenticates using the full v2 API token (`nbt_<key>.<plaintext>`) read from the `token-store` volume, with fallback to the raw secret file.
- Downloaded geographic data is cached in a `geo-foss-cache` volume.

### Generated Files

| File | Description |
|------|-------------|
| `Dockerfile-GeoFoss` | Local build Dockerfile |
| `scripts/run-geo-foss-import.sh` | Import runner script |
| `scripts/import-geo-data.py` | pynetbox-based import implementation |
| `env/geo-foss.env` | Import environment variables |

---

## ORB Discovery

The ORB agent provides network discovery using the official NetBox Labs Orb agent.

### Configuration

| Property | Value |
|----------|-------|
| Compose service | `orb-agent` |
| Compose profile | `orb-discovery` |
| Image | `netboxlabs/orb-agent:2.7.0` |
| Networking | Host networking with `NET_RAW` and `NET_ADMIN` capabilities |

### How It Works

1. The ORB agent runs with host networking and elevated capabilities for active network discovery.
2. Discovery targets RFC1918 ranges (`10/8`, `172.16/12`, `192.168/16`) by default.
3. The scan schedule defaults to `@every 120m` to reduce scan churn.
4. Runs with `dry_run: false` — the `orb-bootstrap` init container injects real Diode client credentials at startup.

### Usage

```bash
docker compose --profile orb-discovery up -d orb-agent
```

!!! note "Automatic Credential Injection"
    The `orb-bootstrap` init container automatically reads `secrets/diode_client_secret`
    and injects it into `configuration/orb/agent.yaml` before `orb-agent` starts.
    No manual credential editing is required.

### Generated Files

| File | Description |
|------|-------------|
| `configuration/orb/agent.yaml` | ORB agent configuration template |
| `scripts/orb-bootstrap.sh` | Init container that injects Diode credentials |
| `env/orb.env` | ORB environment variables |

---

## Diode Services

Diode provides automated network state ingestion and reconciliation into NetBox IPAM.

### Services

| Service | Image | Purpose |
|---------|-------|---------|
| `diode-auth` | `netboxlabs/diode-auth:1.12.0` | OAuth2 introspect service backed by Hydra |
| `diode-ingester` | `netboxlabs/diode-ingester:0.9.0` | gRPC data ingestion service |
| `diode-reconciler` | `netboxlabs/diode-reconciler:1.13.0` | Reconciles ingested state with NetBox objects |
| `diode-proxy` | `nginx:1.27-alpine` | Muxes HTTP/1.1 token/introspect and gRPC on port 18084 |
| `diode-token-adapter` | `python:3.11-alpine` | Translates Hydra JWT `scope` claim for service compatibility |

### How It Works

1. **ORB → diode-proxy (`:18084`)**: ORB sends token requests to `/auth/token` and gRPC ingest to `/`.
2. **diode-proxy → diode-token-adapter**: Token and introspect requests are routed through the adapter, which ensures the RFC 9068 `scope` claim (string) is present in all tokens and introspect responses.
3. **diode-proxy → diode-ingester**: gRPC ingest traffic is forwarded directly.
4. **diode-reconciler → NetBox Diode plugin**: The reconciler calls NetBox `/api/plugins/diode/` to generate and apply change sets.
5. **Hydra `scope_claim: string`**: Configured via `configuration/hydra.yml` to emit `scope` (string) rather than the Hydra default `scp` (array), fixing the root-cause JWT claim mismatch.

### Generated Files

| File | Description |
|------|-------------|
| `configuration/hydra.yml` | Hydra YAML config setting `scope_claim: string` |
| `configuration/diode-proxy.conf` | nginx mux configuration |
| `configuration/diode-token-adapter.py` | Scope-claim translation adapter |
| `scripts/run-diode-ingester.sh` | Diode ingester entrypoint |
| `scripts/run-diode-reconciler.sh` | Diode reconciler entrypoint |
| `scripts/setup-diode-credential.sh` | OAuth2 credential provisioning |
| `env/diode.env` | Diode service environment variables |

---

## Superuser Sync

The superuser sync service creates the pseudonymous bootstrap superuser and mints a v2 API token on first boot.

### Configuration

| Property | Value |
|----------|-------|
| Compose service | `netbox-superuser-sync` |
| Type | One-shot init container |
| Depends on | NetBox health check |

### How It Works

1. Waits for NetBox to become healthy.
2. Creates the bootstrap superuser with the pseudonymous username from `secrets/superuser_name`.
3. Mints a v2 API token using `Token.validate()` for idempotent re-runs.
4. Writes the full v2 token (`nbt_<key>.<plaintext>`) to the `token-store` volume.
5. Sidecar services that depend on `netbox-superuser-sync` can read the assembled token from `token-store`.

### Generated Files

| File | Description |
|------|-------------|
| `scripts/sync-superuser.sh` | Bootstrap superuser creation and token minting |

---

## Wazuh Agent

A Wazuh security observability agent runs with host networking for full host-level visibility.

### Configuration

| Property | Value |
|----------|-------|
| Compose service | `wazuh-agent` |
| Compose profile | `security-observability` |
| Image | `wazuh/wazuh-agent:4.14.4` |
| Network | `network_mode: host` |
