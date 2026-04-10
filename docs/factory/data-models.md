# Data Models

The planner produces a `DeploymentPlan` composed of typed Python dataclasses defined in `models.py`. This page documents every model, field, and type.

## DeploymentPlan

The top-level aggregate model that contains all deployment decisions.

```python
@dataclass(slots=True)
class DeploymentPlan:
    deployment_name: str
    source_report: str
    source_generator_version: str
    host: HostProfile
    sizing: ServiceSizing
    images: ImageSelection
    plugins: list[PluginSpec]
    networks: NetworkProfile
    admin_privacy: AdminPrivacyProfile
    device_type_library: DeviceTypeLibraryProfile
    geo_foss: GeoFossProfile
    monitoring: MonitoringProfile
    identity: IdentityProfile
    tls: TlsProfile
    adjacent_services: list[AdjacentServiceRecommendation]
    warnings: list[str]
    notes: list[str]
```

| Field | Type | Description |
|-------|------|-------------|
| `deployment_name` | `str` | Logical name for the deployment (from `--deployment-name`) |
| `source_report` | `str` | Path to the source JSON report |
| `source_generator_version` | `str` | Version of the netbox-docker workflow baseline |
| `host` | `HostProfile` | Host capabilities derived from the report |
| `sizing` | `ServiceSizing` | Worker count and database tuning |
| `images` | `ImageSelection` | Pinned container images |
| `plugins` | `list[PluginSpec]` | All 11 plugin specifications |
| `networks` | `NetworkProfile` | Network segment allocations |
| `admin_privacy` | `AdminPrivacyProfile` | Bootstrap admin identity |
| `device_type_library` | `DeviceTypeLibraryProfile` | Library import configuration |
| `geo_foss` | `GeoFossProfile` | Geographic data sidecar config |
| `monitoring` | `MonitoringProfile` | Monitoring stack images |
| `identity` | `IdentityProfile` | Identity provider images |
| `tls` | `TlsProfile` | TLS certificate configuration |
| `adjacent_services` | `list[AdjacentServiceRecommendation]` | Recommended FOSS services |
| `warnings` | `list[str]` | Operational warnings |
| `notes` | `list[str]` | Deployment notes |

The `to_dict()` method converts the entire plan to plain dictionaries using `dataclasses.asdict()`.

---

## HostProfile

Host capabilities derived from an `ultimate_info_gather` report.

| Field | Type | Description |
|-------|------|-------------|
| `hostname` | `str` | System hostname |
| `operating_system` | `str` | OS name (e.g. `Ubuntu`) |
| `operating_system_version` | `str` | OS version (e.g. `24.04.4`) |
| `kernel_version` | `str` | Kernel version string |
| `architecture` | `str` | CPU architecture (e.g. `x86_64`) |
| `is_wsl` | `bool` | Whether the host is WSL-based |
| `is_virtual_machine` | `bool` | Whether the host is a VM |
| `hypervisor` | `str \| None` | Hypervisor name if detected |
| `docker_capable` | `bool` | Whether Docker is available |
| `can_install_packages` | `bool` | Whether package installation is available |
| `total_memory_bytes` | `int` | Total system memory in bytes |
| `available_memory_bytes` | `int` | Available system memory in bytes |
| `logical_cores` | `int` | Number of logical CPU cores |
| `default_gateway` | `str \| None` | Default gateway IP |
| `nameservers` | `list[str]` | DNS nameserver list |
| `service_ip` | `str` | Published service IP (default: `127.0.0.1`) |

---

## ServiceSizing

Sizing decisions for the generated deployment, derived from host memory.

| Field | Type | Description |
|-------|------|-------------|
| `profile_name` | `str` | Sizing profile: `small`, `medium`, or `large` |
| `netbox_workers` | `int` | Number of RQ workers per container |
| `netbox_worker_containers` | `int` | Number of worker containers |
| `postgres_shared_buffers` | `str` | PostgreSQL `shared_buffers` setting |
| `postgres_max_connections` | `int` | PostgreSQL `max_connections` setting |
| `housekeeping_interval_minutes` | `int` | NetBox housekeeping task interval |

---

## ImageSelection

Pinned image decisions per lifecycle track.

| Field | Type | Description |
|-------|------|-------------|
| `netbox_image` | `str` | NetBox container image (e.g. `netboxcommunity/netbox:v4.5.7`) |
| `postgres_image` | `str` | PostgreSQL image (track-dependent) |
| `valkey_image` | `str` | Valkey image (track-dependent) |
| `track` | `str` | Lifecycle track: `alpine` or `debian` |
| `release_reference` | `str` | OS release reference string |

---

## PluginSpec

A NetBox plugin selection with compatibility metadata.

| Field | Type | Description |
|-------|------|-------------|
| `package_name` | `str` | PyPI package name |
| `module_name` | `str` | Python module name for `PLUGINS` list |
| `version` | `str` | Pinned version |
| `enabled` | `bool` | Whether the plugin is enabled in the generated bundle |
| `support_tier` | `str` | Compatibility tier (e.g. `supported-community`, `community-beta`) |
| `rationale` | `str` | Why the plugin is enabled or disabled |
| `install_when_disabled` | `bool` | Whether to install the package even when disabled (default: `False`) |
| `config` | `dict[str, Any]` | Plugin configuration for `PLUGINS_CONFIG` |

---

## NetworkProfile

Network planning inputs and computed segment allocations.

| Field | Type | Description |
|-------|------|-------------|
| `cidr_mode` | `str` | CIDR allocation mode: `deterministic` or `dynamic` |
| `segments` | `list[NetworkSegment]` | List of network segment allocations |

## NetworkSegment

A single scoped Docker network segment.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Segment name (e.g. `edge`, `app`, `data`) |
| `cidr` | `str` | CIDR allocation (e.g. `172.30.0.0/27`) |
| `required_hosts` | `int` | Required host capacity |

---

## AdminPrivacyProfile

Anonymous bootstrap admin configuration.

| Field | Type | Description |
|-------|------|-------------|
| `bootstrap_username` | `str` | Pseudonymous username (e.g. `bootstrap-10f19331c8`) |
| `bootstrap_email` | `str` | Email using `.invalid` domain |
| `bootstrap_secret_files` | `list[str]` | List of required secret files |
| `rotation_required` | `bool` | Whether the bootstrap account should be rotated |
| `rationale` | `str` | Explanation of the privacy model |

---

## DeviceTypeLibraryProfile

Pinned NetBox community device-type library import profile.

| Field | Type | Description |
|-------|------|-------------|
| `library_repository` | `str` | GitHub repository URL |
| `library_ref` | `str` | Pinned commit reference |
| `import_service_name` | `str` | Compose service name |
| `vendor_filter_env_var` | `str` | Environment variable for vendor filtering |
| `rationale` | `str` | Import strategy rationale |
| `least_privilege_permissions` | `list[str]` | Required NetBox permissions for import |

---

## GeoFossProfile

NetBox geographic data integration companion service.

| Field | Type | Description |
|-------|------|-------------|
| `repository` | `str` | GitHub repository URL |
| `ref` | `str` | Pinned commit reference |
| `service_name` | `str` | Compose service name |
| `rationale` | `str` | Integration rationale |

---

## MonitoringProfile

Monitoring stack integration from enter-the-metrics.

| Field | Type | Description |
|-------|------|-------------|
| `repository` | `str` | GitHub repository URL |
| `ref` | `str` | Pinned commit reference |
| `grafana_image` | `str` | Grafana image tag |
| `prometheus_image` | `str` | Prometheus image tag |
| `loki_image` | `str` | Loki image tag |
| `alloy_image` | `str` | Alloy image tag |
| `syslog_ng_image` | `str` | syslog-ng image tag |
| `node_exporter_image` | `str` | node-exporter image tag |
| `snmp_exporter_image` | `str` | snmp-exporter image tag |
| `cadvisor_image` | `str` | cAdvisor image tag |
| `rationale` | `str` | Integration rationale |

---

## IdentityProfile

Identity provider configuration for Authentik and Ory Hydra.

| Field | Type | Description |
|-------|------|-------------|
| `authentik_image` | `str` | Authentik server image tag |
| `hydra_image` | `str` | Ory Hydra image tag |
| `rationale` | `str` | Integration rationale |

---

## TlsProfile

TLS certificate provisioning configuration.

| Field | Type | Description |
|-------|------|-------------|
| `mode` | `str` | TLS mode: `self_signed` or `letsencrypt` |
| `fqdn` | `str \| None` | Deployment FQDN (Let's Encrypt mode) |
| `acme_email` | `str \| None` | ACME registration email |
| `dns_provider` | `str \| None` | DNS challenge provider |

---

## AdjacentServiceRecommendation

Recommended adjacent FOSS service for operator workflows.

| Field | Type | Description |
|-------|------|-------------|
| `category` | `str` | Service category (e.g. `identity provider`) |
| `primary_solution` | `str` | Primary recommended solution |
| `primary_url` | `str` | URL for the primary solution |
| `rationale` | `str` | Why this solution is recommended |
| `alternatives` | `list[str]` | Alternative solutions |
| `integration_notes` | `str` | How to integrate with the NetBox deployment |
