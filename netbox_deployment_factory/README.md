# NetBox Deployment Factory

This repository turns `ultimate_info_gather` JSON output into a reproducible NetBox deployment bundle that follows current NetBox Labs and official netbox-docker practices.

All local CI/CD operations are Docker-localized. The host only needs Docker Compose; linting, type checking, tests, and bundle generation run inside the CI image defined in this repository.

The generated bundle is opinionated in five ways:

- NetBox is treated as the source of truth for topology, IPAM, and network automation data.
- The deployment baseline follows the official netbox-docker plugin workflow rather than ad hoc container patterns.
- Plugin enablement is strict: topology and BGP are enabled because they have visible NetBox 4.5 compatibility from official NetBox Community sources.
- Requested plugins are enabled in the generated deployment using upstream compatibility metadata.
- The bootstrap superuser is pseudonymous and secret-file backed so the initial administrative identity is not tied to a human username.
- The community device-type library is included as a separate pinned import workflow that uses the NetBox REST API for idempotent creation of manufacturers, device types (with component templates), module types, and rack types.
- ORB sidecar orchestration metadata and readiness-gated container wiring are generated and deployed by default.

## Version Pins

- NetBox: `4.5.4` as the highest current stable `4.5.x` core patch release
- netbox-docker workflow baseline: `4.0.1`
- Alpine lifecycle reference: `3.23.3`
- Debian lifecycle reference: `13.3 (Trixie)`
- Topology plugin: `netbox-topology-views==4.5.0`
- BGP plugin: `netbox-bgp==0.18.0`
- DNS plugin: `netbox-plugin-dns==1.5.3`
- Config diff plugin: `netbox-config-diff==2.14.0`
- Floorplan plugin: `netbox-floorplan-plugin==0.9.0`
- Inventory plugin: `netbox-inventory==2.5.0`
- Device type library repository: `netbox-community/devicetype-library` pinned by commit `cf50cfe`

## Usage

Generate a Debian bundle through the localized Docker workflow:

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260305_212311.json \
  --output-dir /workspace/generated/current-host-debian \
  --track debian \
  --deployment-name netbox-current-host
```

To generate the Alpine track instead:

```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm factory \
  --report /host-root/generated-report/report_20260305_212311.json \
  --output-dir /workspace/generated/current-host-alpine \
  --track alpine \
  --deployment-name netbox-current-host
```

## What Gets Generated

- `docker-compose.yml`
- `Dockerfile-Plugins`
- `plugin_requirements.txt`
- `configuration/plugins.py`
- `env/netbox.env`
- `env/postgres.env`
- `env/device-type-library-import.env`
- `env/orb.env`
- `secrets/*.example`
- `scripts/run-device-type-library-import.sh`
- `scripts/import-device-type-library.py`
- `scripts/run-orb-agent.sh`
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
- The import service runs as a separate one-shot workload, but the default generated wiring reuses the bootstrap secret set unless you override the import username.
- The bootstrap account is intended only for first login, RBAC setup, and immediate rotation or disablement.

Before the first `docker compose up -d`:

1. Run `docker compose build` to build the local NetBox plugin image used by
   `netbox`, `netbox-worker`, and `orb-agent`.
2. Copy each file in `secrets/*.example` to the same path without the `.example`
   suffix and replace placeholder values with real secrets.

## Least Privilege

- NetBox application services drop all Linux capabilities and enable `no-new-privileges`.
- The device-type-library import runs as a separate one-shot profile inside the NetBox image.
- The importer keeps dropped capabilities and `no-new-privileges`, and downloads the pinned library archive into temporary storage at runtime.
- The importer authenticates against the NetBox REST API using the v2 token from `secrets/superuser_api_token`. If stricter RBAC is required, create a dedicated NetBox user with DCIM add/view permissions and configure a separate token.

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
