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
)
