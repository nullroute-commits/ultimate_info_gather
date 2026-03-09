# Implementation Plan

## Objective

Generate a repository flow that consumes `ultimate_info_gather` output and produces a reproducible, NetBox Labs-aligned Docker deployment bundle for NetBox with topology, BGP, DNS, requested plugin-catalog integrations, ORB sidecar orchestration metadata, NetBox community device-type-library support, Traefik HTTPS reverse proxy, OWASP ModSecurity WAF, scoped Docker networks, Diode auth, and netbox-geo-foss geographic region import.

## Standards Baseline

1. Use the official netbox-docker plugin workflow as the deployment pattern.
2. Keep plugin behavior additive through `PLUGINS` and `PLUGINS_CONFIG` only.
3. Treat NetBox as the network source of truth for topology, IPAM, and automation-facing inventory, and keep unvalidated plugin compatibility claims gated.
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
6. Add a pinned device-type-library import workflow using the NetBox community library and REST API endpoints with v2 token authentication.
7. Create a Docker-localized CI/CD pipeline so linting, typing, tests, and example bundle generation all run in containers.
8. Generate a deployment bundle from the current host report to prove end-to-end functionality.
9. Generate ORB sidecar configuration and compose profile wiring that is gated by NetBox API readiness.
10. Generate netbox-geo-foss sidecar wiring as a profiled one-shot import service that creates a three-tier Region hierarchy (continent → country → city) via the pynetbox REST API, with embedded fallback data for offline environments.
11. Generate a Traefik v3.2 reverse proxy with TLS termination and an auto-generated self-signed certificate (with SAN entries for the host).
12. Generate an OWASP ModSecurity CRS WAF sidecar between Traefik and NetBox to inspect HTTP traffic before it reaches the application.
13. Derive scoped Docker network segments (edge, app, data, security) with explicit CIDR allocations from the deployment plan, using deterministic or dynamic mode.
14. Include Valkey as the Redis-compatible cache and task-queue backend.
15. Include the Diode auth service (`netboxlabs/diode-auth`) in the data network.
16. Generate a superuser-sync one-shot service that creates the pseudonymous bootstrap superuser, mints a v2 API token, and writes the full token (`nbt_<key>.<plaintext>`) to a `token-store` volume for sidecar consumption.

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
- Config drift: enable `netbox-config-diff` 2.14.0 (`min_version=4.5.0`, `max_version=4.5.99`)
- Floorplan: enable `netbox-floorplan-plugin` 0.9.0 (`min_version=4.5.0-beta1`, `max_version=4.5.99`)
- Inventory: enable `netbox-inventory` 2.5.0 (`min_version=4.5.0`)
- Device type library: pin `netbox-community/devicetype-library` by commit and include a dedicated one-shot import service that uses the NetBox REST API with v2 token authentication
- ORB: generate `configuration/orb/orchestration.yml`, `env/orb.env`, and default `orb-agent` wiring through NetBox API readiness checks
- Traefik: generate `configuration/traefik/dynamic.yml`, `scripts/generate-traefik-cert.sh`, and Traefik v3.2 compose service with TLS termination on port 443
- WAF: generate `configuration/waf/default.conf` and OWASP ModSecurity CRS nginx sidecar between Traefik and NetBox
- Scoped networks: derive four isolated Docker bridge networks (edge, app, data, security) with explicit CIDR allocations from `NetworkProfile` in the deployment plan
- Valkey: replace Redis with Valkey as cache and task-queue backend, pinned per lifecycle track
- Diode: include `netboxlabs/diode-auth:latest` in the data network
- Geographic data: include `netbox-geo-foss` as a profiled one-shot sidecar service pinned at commit `50c3c16` that imports a three-tier Region hierarchy (continent → country → city) via pynetbox, with embedded fallback data for 64 countries and ~215 cities
- Superuser sync: generate `scripts/sync-superuser.sh` as a one-shot service that creates the bootstrap superuser, mints a v2 token, and writes the full token to the `token-store` volume
