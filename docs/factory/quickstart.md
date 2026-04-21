# Quickstart

This guide walks through every step from a clean checkout to a running NetBox instance with imported device types and geographic data.

## Prerequisites

- Docker and Docker Compose installed on the target host
- Python 3.11+ (for running `ultimate_info_gather`)
- A Linux host (bare metal, VM, or WSL2)

## Step 1 — Generate a Host Report

Run `ultimate_info_gather` from the repository root to produce a JSON report describing the target host:

```bash
python3 main.py -o ./generated-report -f json
```

The report path (e.g. `generated-report/report_20260309_154959.json`) is used as input to the factory.

## Step 2 — Build the Factory CI Image

```bash
cd netbox_deployment_factory
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml build factory
```

## Step 3 — Generate the Deployment Bundle

=== "Debian (default)"

    ```bash
    docker compose -f docker-compose.ci.yml run --rm factory \
      --report /host-root/generated-report/report_20260309_154959.json \
      --output-dir /workspace/generated/netbox-deploy \
      --host-ip 192.168.1.179 \
      --track debian \
      --deployment-name netbox-deploy
    ```

=== "Alpine"

    ```bash
    docker compose -f docker-compose.ci.yml run --rm factory \
      --report /host-root/generated-report/report_20260309_154959.json \
      --output-dir /workspace/generated/netbox-deploy \
      --host-ip 192.168.1.179 \
      --track alpine \
      --deployment-name netbox-deploy
    ```

=== "Let's Encrypt TLS"

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

If you install the subproject as a package, you can run the standalone factory CLI directly instead of using Docker:

```bash
netbox-deployment-factory --report ./report.json --output-dir ./generated/netbox-deploy
```

## Step 4 — Populate Secrets

Enter the generated bundle directory and create real secret files from the examples:

```bash
cd generated/netbox-deploy/secrets
openssl rand -hex 32 > api_token_pepper_1
openssl rand -base64 24 | tr -d '\n' > db_password
openssl rand -hex 32 > secret_key
openssl rand -base64 24 | tr -d '\n' > superuser_api_token
cp superuser_name.example superuser_name
openssl rand -base64 18 | tr -d '\n' > superuser_password
openssl rand -base64 24 | tr -d '\n' > diode_redis_password
openssl rand -hex 16 > diode_client_id
openssl rand -hex 32 > diode_client_secret
openssl rand -hex 32 > netbox_to_diode
cd ..
```

!!! warning "Identity Profile Secrets"
    If using the `identity` profile, also populate identity secrets:

    ```bash
    cd secrets
    openssl rand -hex 32 > authentik_secret_key
    openssl rand -base64 24 | tr -d '\n' > authentik_pg_password
    openssl rand -base64 24 | tr -d '\n' > hydra_pg_password
    openssl rand -hex 32 > hydra_system_secret
    cd ..
    ```

Keep `superuser_name` aligned with the pseudonymous bootstrap account unless you intentionally change it before first start.

After populating secrets, update the `replace-me` credential placeholders in `env/diode.env`:

| Env variable | Matching secret file |
|---|---|
| `REDIS_PASSWORD` | `secrets/diode_redis_password` |
| `POSTGRES_PASSWORD` | `secrets/db_password` |
| `DIODE_TO_NETBOX_CLIENT_SECRET` | `secrets/netbox_to_diode` |

!!! note "Hydra env placeholders"
    The `env/hydra.env` file also contains `replace-me` placeholders (`DSN` and `SECRETS_SYSTEM`), but the Hydra compose services override these at runtime by reading from Docker secrets (`hydra_pg_password` and `hydra_system_secret`), so no manual replacement is required there.

## Step 5 — Build Images

Build the custom NetBox plugin image and the geo-foss sidecar:

```bash
docker compose build
```

## Step 6 — Start the Stack

```bash
docker compose up -d
```

On first boot, NetBox runs database migrations before it becomes healthy. Dependent services (workers, WAF, Traefik, superuser sync) wait for the NetBox health check to pass. This typically takes 2–5 minutes.

Check progress:

```bash
docker compose ps
docker logs netbox-deploy-netbox-1 --tail 20
```

Once NetBox shows `(healthy)`, all dependent containers should start automatically. If any remain in `Created` state, re-run:

```bash
docker compose up -d
```

## Step 6b — Populate Cloudflare DNS Token (Let's Encrypt Only)

If the bundle was generated with `--fqdn`, create the Cloudflare API token secret:

```bash
cd generated/netbox-deploy/secrets
echo -n 'your-cloudflare-dns-api-token' > cf_dns_api_token
cd ..
```

The token needs `Zone:DNS:Edit` permission for the zone containing the FQDN.

## Step 7 — Access NetBox

NetBox is available at **https://&lt;host-ip&gt;** (port 443).

- **Self-signed mode** (default): The TLS certificate is auto-generated by the `traefik-certgen` init container.
- **Let's Encrypt mode** (`--fqdn`): Traefik obtains a trusted certificate via ACME DNS-01 challenge. Access NetBox at `https://<fqdn>` instead.

!!! tip "WSL Users"
    When the generator runs inside WSL or another guest environment, pass `--host-ip <windows-or-lan-ip>` so published ports, public URLs, and identity redirects use the real host address instead of the guest NAT address.

Log in with:

- **Username**: the value in `secrets/superuser_name` (e.g. `bootstrap-10f19331c8`)
- **Password**: the value in `secrets/superuser_password`

The bootstrap account is intended only for first login and RBAC setup — rotate or disable it after creating named operator accounts.

## Step 8 — Import Device-Type Library (Optional)

```bash
docker compose --profile device-type-library-import run --rm device-type-library-import
```

To import only specific vendors:

```bash
docker compose --profile device-type-library-import run \
  -e DEVICE_TYPE_LIBRARY_VENDORS=cisco,juniper \
  device-type-library-import
```

See [Sidecar Services](sidecars.md#device-type-library-import) for details.

## Step 9 — Import Geographic Data (Optional)

```bash
docker compose build netbox-geo-foss
docker compose --profile geo-foss-import run --rm netbox-geo-foss
```

Set `GEONAMES_USERNAME` in `env/geo-foss.env` to a valid GeoNames account for live API data. Without it, the import falls back to an embedded dataset of 64 countries and ~215 cities.

See [Sidecar Services](sidecars.md#geographic-data-netbox-geo-foss) for details.

## Step 10 — Start the Monitoring Stack (Optional)

```bash
./scripts/fetch-monitoring-dashboards.sh
docker compose --profile monitoring up -d
```

Grafana is available at **http://<host-ip>:3000** with the default `admin`/`admin` credentials. Change the password on first login.

See [Monitoring Stack](monitoring.md) for details.

## Step 11 — Start the Identity Stack (Optional)

```bash
docker compose --profile identity up -d
```

Populate `secrets/authentik_secret_key`, `secrets/authentik_pg_password`, `secrets/hydra_pg_password`, and `secrets/hydra_system_secret` before starting.

See [Identity Stack](identity.md) for details.

## What's Next

- [CLI Reference](cli-reference.md) — all available flags and advanced usage
- [Security & Privacy](security.md) — understand the privacy model and secret management
- [Plugin Catalog](plugins.md) — review enabled and disabled plugins
- [Troubleshooting](troubleshooting.md) — common issues and solutions
