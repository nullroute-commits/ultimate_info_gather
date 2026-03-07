# Feature Alignment

## Topology

The repository enables `netbox-topology-views` because topology visualization is a direct modeling extension and the plugin documents NetBox 4.5 compatibility. The generated configuration enables coordinate persistence and creates the expected static image directory in the custom image.

## BGP

The repository enables `netbox-bgp` because it directly extends NetBox as a source of truth for BGP sessions, peer groups, policy, and AS-path artifacts. The generated configuration exposes the BGP data on a device tab and enables a top-level menu.

## DNS

The repository does not enable a DNS plugin by default. The last hard-coded `netbox-dns` pin was not reproducible from the official `netbox-community` GitHub organization and did not match an installable package release. To keep the generated bundle aligned with NetBox Labs installation guidance and official NetBox Community sources, DNS is now treated as an explicit gap rather than a silently broken default.

## Device-Type Library

The repository includes the NetBox community device-type library as a pinned external content source rather than an in-application plugin. The generated deployment bundle now uses NetBox core's own bulk-import views for manufacturers, rack types, device types, and module types instead of the older external `Device-Type-Library-Import` helper. The import runs as a dedicated one-shot service with dropped capabilities and `no-new-privileges`, downloads the pinned library archive into temporary storage, and submits YAML through first-party NetBox import paths. By default, the generated import identity is read from `superuser_name`, but operators can override `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE` to use a dedicated user.

## API Tokens

The repository now generates an `api_token_pepper_1` secret alongside the bootstrap secrets so NetBox can mint and validate current v2 API tokens. Because the generated device-type importer now runs inside Django and uses NetBox's native bulk-import views, the bundle no longer needs to mint a legacy v1 API token just to support an older external importer.

## CI/CD Localization

The repository localizes CI/CD into Docker. Local validation and GitHub Actions both use `docker compose -f docker-compose.ci.yml` so linting, type checking, tests, and sample bundle generation run inside the repository's CI image rather than relying on host Python tooling. Bundle artifacts are written back into the workspace under `.artifacts/` so the same containerized flow works locally and in CI.
