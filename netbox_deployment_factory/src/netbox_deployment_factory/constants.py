"""Version pins and plugin defaults for NetBox 4.5 deployments.

All infrastructure images are pinned to the latest stable release.
Components that have only a single active major line (e.g. node-exporter v1,
cAdvisor v0) keep their current major and are pinned to the latest stable
patch.

Compatibility matrix:
  - PostgreSQL 18 is the latest major and is supported by NetBox 4.5,
    Authentik 2026, and Ory Hydra v2.
  - Valkey 9 is the latest major and is supported by NetBox 4.5
    (requires Redis/Valkey >= 6).
  - Grafana 12 is the latest major and works with Prometheus v3 and
    Loki 3 datasources.
  - Loki 3.7 and Alloy v1.15 are the current monitoring stack pins.
  - Prometheus v3 is the latest major.
  - Authentik 2026 is the latest year-based major.
  - Traefik v3, Hydra v2, syslog-ng 4 remain on their current major
    because prior majors are end-of-life or API-incompatible.
"""

from __future__ import annotations

from .models import PluginSpec

NETBOX_VERSION = "4.5.7"
NETBOX_DOCKER_WORKFLOW_VERSION = "4.0.2"
ALPINE_RELEASE = "3.23.3"
DEBIAN_RELEASE = "13.3 (Trixie)"
NETBOX_IMAGE = f"netboxcommunity/netbox:v{NETBOX_VERSION}"
ORB_AGENT_IMAGE = "netboxlabs/orb-agent:2.7.0"
DIODE_AUTH_IMAGE = "netboxlabs/diode-auth:1.12.0"
DIODE_INGESTER_IMAGE = "netboxlabs/diode-ingester:1.13.0"
DIODE_RECONCILER_IMAGE = "netboxlabs/diode-reconciler:1.13.0"
DEVICE_TYPE_LIBRARY_REPOSITORY = "https://github.com/netbox-community/devicetype-library.git"
DEVICE_TYPE_LIBRARY_REF = "cf50cfe"

GEO_FOSS_REPOSITORY = "https://github.com/nullroute-commits/netbox-geo-foss.git"
GEO_FOSS_REF = "50c3c16"

MONITORING_REPOSITORY = "https://github.com/nullroute-commits/enter-the-metrics.git"
MONITORING_REF = "706ed92"

GRAFANA_IMAGE = "grafana/grafana:12.4.2"
PROMETHEUS_IMAGE = "prom/prometheus:v3.11.0"
LOKI_IMAGE = "grafana/loki:3.7.1"
ALLOY_IMAGE = "grafana/alloy:v1.15.0"
SYSLOG_NG_IMAGE = "balabit/syslog-ng:4.11.0"
NODE_EXPORTER_IMAGE = "prom/node-exporter:v1.11.1"
SNMP_EXPORTER_IMAGE = "prom/snmp-exporter:v0.30.1"
CADVISOR_IMAGE = "gcr.io/cadvisor/cadvisor:v0.52.1"

# --- Edge / Security ---------------------------------------------------------
TRAEFIK_IMAGE = "traefik:v3.6.13"
WAF_IMAGE = "owasp/modsecurity-crs:4.25.0-nginx-lts"
OPENSSL_IMAGE = "alpine/openssl:3.5.5"

# --- Identity ----------------------------------------------------------------
AUTHENTIK_IMAGE = "ghcr.io/goauthentik/server:2026.2.2"
HYDRA_IMAGE = "oryd/hydra:v2.3.0"

# --- Security / Observability ------------------------------------------------
WAZUH_MANAGER_IMAGE = "wazuh/wazuh-manager:4.14.4"
WAZUH_AGENT_IMAGE = "wazuh/wazuh-agent:4.14.4"
MONITORING_INIT_IMAGE = "alpine:3.23"
NGINX_IMAGE = "nginx:1.27-alpine"

TRACK_IMAGE_DEFAULTS: dict[str, dict[str, str]] = {
    "alpine": {
        "postgres_image": "postgres:18-alpine",
        "valkey_image": "valkey/valkey:9-alpine",
        "release_reference": f"Alpine Linux {ALPINE_RELEASE}",
    },
    "debian": {
        "postgres_image": "postgres:18",
        "valkey_image": "valkey/valkey:9",
        "release_reference": f"Debian {DEBIAN_RELEASE}",
    },
}

DEFAULT_PLUGIN_SPECS: tuple[PluginSpec, ...] = (
    PluginSpec(
        package_name="netbox-topology-views",
        module_name="netbox_topology_views",
        version="4.5.1",
        enabled=True,
        support_tier="supported-community",
        rationale=(
            "Explicit NetBox 4.5.x compatibility and common topology "
            "visualization requirement."
        ),
        config={
            "static_image_directory": "netbox_topology_views/img",
            "allow_coordinates_saving": True,
            "always_save_coordinates": True,
        },
    ),
    PluginSpec(
        package_name="netbox-bgp",
        module_name="netbox_bgp",
        version="0.18.1",
        enabled=True,
        support_tier="supported-community",
        rationale="Explicit NetBox 4.5.x compatibility for BGP data modeling.",
        config={
            "device_ext_page": "tab",
            "top_level_menu": True,
        },
    ),
    PluginSpec(
        package_name="netbox-plugin-dns",
        module_name="netbox_dns",
        version="1.5.5",
        enabled=True,
        support_tier="supported-community",
        rationale=(
            "Explicit NetBox 4.5.0+ compatibility (min_version='4.5.0'). "
            "Provides DNS zone, record, and nameserver management natively "
            "inside NetBox, enabling DNS as a first-class part of the network "
            "source of truth alongside IPAM and topology data."
        ),
        config={},
    ),
    PluginSpec(
        package_name="netbox-acls",
        module_name="netbox_acls",
        version="2.0.0",
        enabled=True,
        support_tier="supported-community",
        rationale=(
            "Official netbox-community plugin and package. Version 2.0.0 "
            "explicitly targets NetBox 4.5.x in the upstream compatibility "
            "matrix."
        ),
        config={
            "top_level_menu": True,
        },
    ),
    PluginSpec(
        package_name="netbox-reorder-rack",
        module_name="netbox_reorder_rack",
        version="1.1.4",
        enabled=True,
        support_tier="community",
        rationale=(
            "Community rack layout tooling that exposes drag-and-drop rack "
            "reordering. Upstream compatibility matrix states >=4.0.0."
        ),
        config={},
    ),
    PluginSpec(
        package_name="netbox-prometheus-sd",
        module_name="netbox_prometheus_sd",
        version="0.5",
        enabled=False,
        support_tier="community-legacy",
        rationale=(
            "Provides Prometheus HTTP SD endpoints for NetBox devices, but "
            "the current release imports legacy 'extras.plugins' and fails to "
            "load on NetBox 4.5.x. Kept disabled until an updated release "
            "targets modern NetBox plugin APIs."
        ),
        config={
            "custom_field_name": "monitored",
            "target_port": 9100,
            "gnmic_target_port": 32767,
        },
    ),
    PluginSpec(
        package_name="netboxlabs-diode-netbox-plugin",
        module_name="netbox_diode_plugin",
        version="1.9.0",
        enabled=True,
        support_tier="supported-netboxlabs",
        rationale=(
            "Official NetBox Labs Diode plugin. Upstream compatibility table "
            "shows NetBox >= 4.5.0 support. The generated bundle includes "
            "Diode auth/ingester/reconciler services by default so the plugin "
            "target resolves and reconciliation APIs are available on first "
            "start."
        ),
        config={
            "diode_username": "diode",
            "diode_target_override": "grpc://diode-proxy:80",
            "secrets_path": "/run/secrets/",
            "netbox_to_diode_client_id": "netbox-to-diode",
            "netbox_to_diode_client_secret_name": "netbox_to_diode",
        },
    ),
    PluginSpec(
        package_name="netbox-proxbox",
        module_name="netbox_proxbox",
        version="0.0.10",
        enabled=True,
        support_tier="community",
        rationale=(
            "Integrates Proxmox VE inventory (clusters, nodes, VMs, containers) "
            "with NetBox as the network source of truth. Version 0.0.10 "
            "explicitly lists NetBox 4.5.x in its requirements."
        ),
        config={},
    ),
    PluginSpec(
        package_name="netbox-config-diff",
        module_name="netbox_config_diff",
        version="2.14.2",
        enabled=False,
        support_tier="community",
        rationale=(
            "Requested integration from https://github.com/miaow2/netbox-config-diff. "
            "Upstream PluginConfig declares min_version='4.5.0' and max_version='4.5.99'. "
            "Disabled by default: v2.14.2 triggers a strawberry "
            "DuplicatedTypeName('StrFilterLookup') error on NetBox 4.5.7 that "
            "prevents the application from starting. Re-enable when upstream "
            "releases a compatible version."
        ),
        config={
            "USERNAME": "replace-me",
            "PASSWORD": "replace-me",
        },
    ),
    PluginSpec(
        package_name="netbox-floorplan-plugin",
        module_name="netbox_floorplan",
        version="0.9.1",
        enabled=True,
        support_tier="community",
        rationale=(
            "Requested integration from "
            "https://github.com/netbox-community/netbox-floorplan-plugin. "
            "Upstream PluginConfig declares min_version='4.5.0-beta1' and max_version='4.5.99'."
        ),
        config={},
    ),
    PluginSpec(
        package_name="netbox-inventory",
        module_name="netbox_inventory",
        version="2.5.1",
        enabled=True,
        support_tier="community",
        rationale=(
            "Requested integration from https://github.com/ArnesSI/netbox-inventory. "
            "Upstream PluginConfig declares min_version='4.5.0'."
        ),
        config={},
    ),
)
