"""Version pins and plugin defaults for NetBox 4.5 deployments."""

from __future__ import annotations

from .models import PluginSpec

NETBOX_VERSION = "4.5.4"
NETBOX_DOCKER_WORKFLOW_VERSION = "4.0.1"
ALPINE_RELEASE = "3.23.3"
DEBIAN_RELEASE = "13.3 (Trixie)"
NETBOX_IMAGE = f"netboxcommunity/netbox:v{NETBOX_VERSION}"
DEVICE_TYPE_LIBRARY_REPOSITORY = "https://github.com/netbox-community/devicetype-library.git"
DEVICE_TYPE_LIBRARY_REF = "cf50cfe"

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
        version="4.5.0",
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
        version="0.18.0",
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
        version="1.5.3",
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
        version="1.9.1",
        enabled=False,
        support_tier="supported-community",
        rationale=(
            "Official netbox-community plugin and package, but the current "
            "plugin config declares max_version='4.4.99'. It is intentionally "
            "disabled on NetBox 4.5.x until a compatible release exists."
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
        version="1.7.1",
        enabled=True,
        support_tier="supported-netboxlabs",
        rationale=(
            "Official NetBox Labs Diode plugin. Upstream declares "
            "min_version='4.4.10' and max_version='4.5.99'."
        ),
        config={
            "diode_username": "diode",
            "diode_target_override": "grpc://diode:8080/diode",
            "secrets_path": "/run/secrets/",
        },
    ),
    PluginSpec(
        package_name="netbox-proxbox",
        module_name="netbox_proxbox",
        version="0.0.6b2",
        enabled=False,
        support_tier="community-beta",
        rationale=(
            "Integrates Proxmox VE inventory (clusters, nodes, VMs, containers) "
            "with NetBox as the network source of truth. This plugin is the "
            "proxmox-netboxlabs solution for Proxmox–NetBox synchronization. "
            "Currently disabled because the latest release (0.0.6b2) declares "
            "max_version='4.2.99', making it incompatible with the pinned "
            "NetBox 4.5.x image. Enable once an officially supported release "
            "targeting NetBox 4.5 is available, or when using a NetBox 4.2.x "
            "deployment track."
        ),
        config={},
    ),
    PluginSpec(
        package_name="netbox-config-diff",
        module_name="netbox_config_diff",
        version="2.14.0",
        enabled=True,
        support_tier="community",
        rationale=(
            "Requested integration from https://github.com/miaow2/netbox-config-diff. "
            "Upstream PluginConfig declares min_version='4.5.0' and max_version='4.5.99'."
        ),
        config={
            "USERNAME": "replace-me",
            "PASSWORD": "replace-me",
        },
    ),
    PluginSpec(
        package_name="netbox-floorplan-plugin",
        module_name="netbox_floorplan",
        version="0.9.0",
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
        version="2.5.0",
        enabled=True,
        support_tier="community",
        rationale=(
            "Requested integration from https://github.com/ArnesSI/netbox-inventory. "
            "Upstream PluginConfig declares min_version='4.5.0'."
        ),
        config={},
    ),
)
