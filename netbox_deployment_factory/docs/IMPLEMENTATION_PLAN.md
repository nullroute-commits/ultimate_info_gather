# Implementation Plan

## Objective

Generate a new repository that consumes `ultimate_info_gather` output and produces a reproducible, NetBox Labs-aligned Docker deployment bundle for NetBox with topology, BGP, and NetBox community device-type-library support, while surfacing DNS as a documented integration gap until an official-community-backed source path is validated.

## Standards Baseline

1. Use the official netbox-docker plugin workflow as the deployment pattern.
2. Keep plugin behavior additive through `PLUGINS` and `PLUGINS_CONFIG` only.
3. Treat NetBox as the network source of truth for topology, IPAM, and automation-facing inventory, and document any unsupported DNS integration gaps explicitly.
4. Use the NetBox community device-type library as a separately pinned import workflow rather than bundling ad hoc data.
5. Protect the bootstrap admin identity by making it pseudonymous and secret-file backed.
6. Enforce least privilege by separating database and admin secrets, using the NetBox token pepper model, and dropping unnecessary container capabilities.
7. Localize all CI/CD execution into Docker so hosts and runners need only Docker Compose.

## Execution Plan

1. Parse the `ultimate_info_gather` JSON report into a typed host profile.
2. Derive sizing and operational warnings from observed host memory, Docker capability, WSL detection, and DNS-plugin policy.
3. Pin NetBox, plugin, and service image versions for Debian and Alpine lifecycle tracks.
4. Render a compose bundle patterned after netbox-docker with a custom plugin image.
5. Generate additive plugin configuration only for plugins that can be pinned to official NetBox Community sources and installable release artifacts.
6. Add a pinned device-type-library import workflow using the NetBox community library and NetBox core bulk-import views.
7. Create a Docker-localized CI/CD pipeline so linting, typing, tests, and example bundle generation all run in containers.
8. Generate a deployment bundle from the current host report to prove end-to-end functionality.

## Current Host Findings

- Platform: Ubuntu 24.04.4 on WSL2
- Container capability: available through Docker
- Package installation capability: not directly available through the collector result
- Available memory: about 1 GiB free on a 4 GiB host
- Operational implication: use a small profile with one NetBox worker and conservative PostgreSQL defaults

## Feature Mapping

- Topology: enable `netbox-topology-views`
- BGP: enable `netbox-bgp`
- DNS: enable `netbox-plugin-dns` 1.5.3 (explicit NetBox 4.5.0+ support, official netbox-community source)
- Proxmox: include `netbox-proxbox` 0.0.6b2 in the plugin spec list but disable by default due to `max_version='4.2.99'` incompatibility with NetBox 4.5; document the NetBox Labs event-driven automation alternative
- Device type library: pin `netbox-community/devicetype-library` by commit and include a dedicated one-shot import service that uses NetBox core bulk import
