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

The generated bundle includes an ORB sidecar service in the default Compose deployment:

- Compose service: `orb-agent`
- Env file: `env/orb.env`
- Entrypoint script: `scripts/run-orb-agent.sh`
- Metadata: `configuration/orb/orchestration.yml`

The sidecar waits for NetBox API readiness (`/api/status/`) using the secret-backed token file, records the generated orchestration metadata path, and then stays alive as a readiness-gated placeholder sidecar. This keeps orchestration flow NetBox-gated without changing NetBox core behavior while leaving room for future ORB polling logic.

## Device-Type Library

The repository includes the NetBox community device-type library as a pinned external content source rather than an in-application plugin. The generated deployment bundle uses the **NetBox REST API** to create manufacturers, device types (with full component templates), module types, and rack types. The import runs as a dedicated one-shot Compose profile service (`device-type-library-import`) with dropped capabilities and `no-new-privileges`, downloads the library archive into temporary storage, parses YAML definitions, and creates objects through `/api/dcim/` endpoints with v2 Bearer token authentication.

Key features of the REST API importer:
- **Component templates**: Creates interface, console-port, power-port, power-outlet, rear-port, front-port, device-bay, module-bay, and inventory-item templates for each device/module type.
- **Idempotent**: Existing objects are looked up by slug (or model+manufacturer for module types) and skipped. Re-running the import produces no duplicates.
- **Vendor filtering**: Set `DEVICE_TYPE_LIBRARY_VENDORS` to a comma-separated list of vendor directory names (e.g., `cisco,juniper`) to import only specific vendors.
- **Bulk creation**: Component templates are POSTed in batches for efficiency.

## API Tokens

The repository generates an `api_token_pepper_1` secret alongside the bootstrap secrets so NetBox can mint and validate v2 API tokens. The superuser sync script creates a v2 token from the `superuser_api_token` secret file using Token.validate() for idempotent re-runs. The device-type importer authenticates with `Authorization: Bearer nbt_<key>.<plaintext>` format, where the key (HMAC digest) is read from the Token ORM and the plaintext comes from the mounted secret file.

## CI/CD Localization

The repository localizes CI/CD into Docker. Local validation and GitHub Actions both use `docker compose -f docker-compose.ci.yml` so linting, type checking, tests, and sample bundle generation run inside the repository's CI image rather than relying on host Python tooling. Bundle artifacts are written back into the workspace under `.artifacts/` so the same containerized flow works locally and in CI.
