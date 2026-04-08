# CLI Reference

The factory CLI is invoked via `python -m netbox_deployment_factory` or through the Docker CI workflow. This page documents all available flags.

## Usage

```bash
python -m netbox_deployment_factory \
  --report <path> \
  --output-dir <path> \
  [options]
```

Or via Docker:

```bash
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/<path> \
  --output-dir /workspace/<path> \
  [options]
```

## Flag Reference

| Flag | Type | Default | Required | Description |
|------|------|---------|----------|-------------|
| `--report` | path | — | Yes | Path to the `ultimate_info_gather` JSON report |
| `--output-dir` | path | — | Yes | Directory where the deployment bundle should be written |
| `--track` | choice | `debian` | No | Image lifecycle track: `alpine` or `debian` |
| `--deployment-name` | string | `netbox-stack` | No | Logical name for the generated deployment |
| `--cidr-mode` | choice | `deterministic` | No | CIDR planning mode for Docker networks: `deterministic` or `dynamic` |
| `--edge-hosts` | int | `16` | No | Required host capacity for the edge network (dynamic mode) |
| `--app-hosts` | int | `16` | No | Required host capacity for the app network (dynamic mode) |
| `--data-hosts` | int | `16` | No | Required host capacity for the data network (dynamic mode) |
| `--security-hosts` | int | `8` | No | Required host capacity for the security network (dynamic mode) |
| `--worker-containers` | int | *(auto)* | No | Override the number of NetBox worker containers (defaults to host-derived sizing profile) |
| `--host-ip` | string | *(auto-detected)* | No | Override the detected published host IP used for bound ports, public URLs, and related generated configuration |
| `--fqdn` | string | *(none)* | No | Fully qualified domain name for the deployment. Enables Let's Encrypt ACME DNS-01 via Cloudflare (requires `--acme-email`) |
| `--acme-email` | string | *(none)* | No | Email address for Let's Encrypt ACME registration (required when `--fqdn` is provided) |

## Examples

### Basic Debian Bundle

```bash
python -m netbox_deployment_factory \
  --report report.json \
  --output-dir ./deploy \
  --host-ip 192.168.1.100 \
  --deployment-name my-netbox
```

### Alpine Track

```bash
python -m netbox_deployment_factory \
  --report report.json \
  --output-dir ./deploy \
  --host-ip 192.168.1.100 \
  --track alpine \
  --deployment-name my-netbox
```

### Dynamic Network Sizing

```bash
python -m netbox_deployment_factory \
  --report report.json \
  --output-dir ./deploy \
  --cidr-mode dynamic \
  --edge-hosts 60 \
  --app-hosts 30 \
  --data-hosts 12 \
  --security-hosts 8
```

### Let's Encrypt TLS with Custom Workers

```bash
python -m netbox_deployment_factory \
  --report report.json \
  --output-dir ./deploy \
  --host-ip 203.0.113.10 \
  --fqdn netbox.example.com \
  --acme-email admin@example.com \
  --worker-containers 3
```

### Docker CI Workflow

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report.json \
  --output-dir /workspace/generated/netbox-deploy \
  --host-ip 192.168.1.179 \
  --track debian \
  --deployment-name netbox-deploy
```

Setting `LOCAL_UID` and `LOCAL_GID` keeps generated files owned by the invoking host user instead of container root.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `NETBOX_DEPLOY_HOST_IP` | Alternative to `--host-ip`. The CLI flag takes precedence if both are set. |

## Lifecycle Tracks

The `--track` flag selects the base OS images for PostgreSQL and Valkey:

| Track | PostgreSQL Image | Valkey Image | OS Reference |
|-------|-----------------|-------------|-------------|
| `debian` | `postgres:18` | `valkey/valkey:9` | Debian 13.3 (Trixie) |
| `alpine` | `postgres:18-alpine` | `valkey/valkey:9-alpine` | Alpine Linux 3.23.3 |

Both tracks use the same NetBox image (`netboxcommunity/netbox:v4.5.4`).

## CIDR Modes

### Deterministic (default)

Uses fixed CIDR blocks from `172.30.0.0/24`:

| Segment | CIDR |
|---------|------|
| edge | `172.30.0.0/27` |
| app | `172.30.0.32/27` |
| data | `172.30.0.64/27` |
| security | `172.30.0.96/28` |
| monitoring | `172.30.0.128/27` |
| identity | `172.30.0.160/27` |

### Dynamic

Allocates segments from `172.31.0.0/16` with prefix lengths sized to the required host count. The `--edge-hosts`, `--app-hosts`, `--data-hosts`, and `--security-hosts` flags control segment sizes.

!!! note "Monitoring and identity segments"
    The monitoring and identity segments default to 16 hosts and are not currently exposed as CLI flags. They are always allocated in both CIDR modes.
