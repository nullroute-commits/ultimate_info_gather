"""Build deployment plans from ultimate_info_gather reports."""

from __future__ import annotations

import copy
import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any, cast

from .constants import (
    DEFAULT_PLUGIN_SPECS,
    DEVICE_TYPE_LIBRARY_REF,
    DEVICE_TYPE_LIBRARY_REPOSITORY,
    NETBOX_DOCKER_WORKFLOW_VERSION,
    NETBOX_IMAGE,
    TRACK_IMAGE_DEFAULTS,
)
from .models import (
    AdminPrivacyProfile,
    DeploymentPlan,
    DeviceTypeLibraryProfile,
    HostProfile,
    ImageSelection,
    NetworkProfile,
    NetworkSegment,
    PluginSpec,
    ServiceSizing,
)


def load_report(report_path: Path | str) -> dict[str, Any]:
    """Load a collector report from disk."""

    path = Path(report_path)
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _build_host_profile(report: dict[str, Any]) -> HostProfile:
    environment = report["environment"]
    software = report["software"]
    hardware = report["hardware"]
    network = report["network"]

    os_info = software["os_info"]
    memory = hardware["memory"]
    docker_capable = software.get("can_manage_containers", False) and (
        "docker" in software.get("container_runtimes", [])
    )

    return HostProfile(
        hostname=environment["hostname"],
        operating_system=os_info["name"],
        operating_system_version=os_info["version"],
        kernel_version=os_info["kernel_version"],
        architecture=os_info["architecture"],
        is_wsl=environment["is_wsl"],
        is_virtual_machine=hardware["is_virtual_machine"],
        hypervisor=hardware["hypervisor"],
        docker_capable=docker_capable,
        can_install_packages=software.get("can_install_packages", False),
        total_memory_bytes=memory["total_bytes"],
        available_memory_bytes=memory["available_bytes"],
        logical_cores=hardware["cpu"]["logical_cores"],
        default_gateway=network.get("default_gateway"),
        nameservers=network.get("dns_config", {}).get("nameservers", []),
    )


def _derive_sizing(host: HostProfile) -> ServiceSizing:
    total_gib = host.total_memory_bytes / (1024**3)

    if total_gib < 6:
        return ServiceSizing(
            profile_name="small",
            netbox_workers=1,
            netbox_worker_containers=1,
            postgres_shared_buffers="256MB",
            postgres_max_connections=200,
            housekeeping_interval_minutes=30,
        )
    if total_gib < 12:
        return ServiceSizing(
            profile_name="medium",
            netbox_workers=2,
            netbox_worker_containers=2,
            postgres_shared_buffers="512MB",
            postgres_max_connections=300,
            housekeeping_interval_minutes=20,
        )
    return ServiceSizing(
        profile_name="large",
        netbox_workers=4,
        netbox_worker_containers=4,
        postgres_shared_buffers="1GB",
        postgres_max_connections=500,
        housekeeping_interval_minutes=15,
    )


def _derive_admin_privacy(report: dict[str, Any]) -> AdminPrivacyProfile:
    report_id = report["report_metadata"]["report_id"]
    alias_seed = hashlib.sha256(report_id.encode("utf-8")).hexdigest()[:10]
    bootstrap_username = f"bootstrap-{alias_seed}"

    return AdminPrivacyProfile(
        bootstrap_username=bootstrap_username,
        bootstrap_email=f"{bootstrap_username}@invalid.local",
        bootstrap_secret_files=[
            "api_token_pepper_1",
            "secret_key",
            "db_password",
            "superuser_name",
            "superuser_password",
            "superuser_api_token",
        ],
        rotation_required=True,
        rationale=(
            "Use a pseudonymous bootstrap superuser that is not tied to a human identity, "
            "store the credentials only in separate local secret files, and disable "
            "or rotate the account after creating named RBAC-backed operators."
        ),
    )


def _derive_device_type_library_profile() -> DeviceTypeLibraryProfile:
    return DeviceTypeLibraryProfile(
        library_repository=DEVICE_TYPE_LIBRARY_REPOSITORY,
        library_ref=DEVICE_TYPE_LIBRARY_REF,
        import_service_name="device-type-library-import",
        vendor_filter_env_var="DEVICE_TYPE_LIBRARY_VENDORS",
        rationale=(
            "Use the NetBox community device-type library as a pinned source and "
            "run imports through NetBox core's own bulk-import workflow inside a "
            "dedicated one-shot container."
        ),
        least_privilege_permissions=[
            "dcim.add_manufacturer",
            "dcim.view_manufacturer",
            "dcim.add_devicetype",
            "dcim.view_devicetype",
            "dcim.add_moduletype",
            "dcim.view_moduletype",
            "dcim.add_racktype",
            "dcim.view_racktype",
            "dcim.add_consoleporttemplate",
            "dcim.add_consoleserverporttemplate",
            "dcim.add_powerporttemplate",
            "dcim.add_poweroutlettemplate",
            "dcim.add_interfacetemplate",
            "dcim.add_frontporttemplate",
            "dcim.add_rearporttemplate",
            "dcim.add_modulebaytemplate",
            "dcim.add_devicebaytemplate",
            "dcim.add_inventoryitemtemplate",
        ],
    )


def _select_plugins() -> list[PluginSpec]:
    return [copy.deepcopy(spec) for spec in DEFAULT_PLUGIN_SPECS]


def _prefix_for_required_hosts(required_hosts: int) -> int:
    if required_hosts < 2:
        required_hosts = 2

    host_bits = 2
    while (2**host_bits - 2) < required_hosts:
        host_bits += 1

    return 32 - host_bits


def _derive_network_profile(
    cidr_mode: str,
    required_hosts: dict[str, int] | None = None,
) -> NetworkProfile:
    defaults = {
        "edge": 16,
        "app": 16,
        "data": 16,
        "security": 8,
    }
    requested = defaults | (required_hosts or {})

    if cidr_mode == "deterministic":
        return NetworkProfile(
            cidr_mode=cidr_mode,
            segments=[
                NetworkSegment(
                    name="edge",
                    cidr="172.30.0.0/27",
                    required_hosts=requested["edge"],
                ),
                NetworkSegment(
                    name="app",
                    cidr="172.30.0.32/27",
                    required_hosts=requested["app"],
                ),
                NetworkSegment(
                    name="data",
                    cidr="172.30.0.64/27",
                    required_hosts=requested["data"],
                ),
                NetworkSegment(
                    name="security",
                    cidr="172.30.0.96/28",
                    required_hosts=requested["security"],
                ),
            ],
        )

    if cidr_mode != "dynamic":
        raise ValueError("Unsupported cidr_mode. Expected one of: deterministic, dynamic")

    base_start = int(ipaddress.IPv4Address("172.31.0.0"))
    base_end = int(ipaddress.IPv4Address("172.31.255.255"))
    cursor = base_start
    segments: list[NetworkSegment] = []

    for name in ("edge", "app", "data", "security"):
        prefix = _prefix_for_required_hosts(requested[name])
        block_size = 2 ** (32 - prefix)

        remainder = cursor % block_size
        if remainder:
            cursor += block_size - remainder

        if cursor + block_size - 1 > base_end:
            raise ValueError("Requested dynamic network sizing exceeds 172.31.0.0/16")

        cidr = f"{ipaddress.IPv4Address(cursor)}/{prefix}"
        segments.append(NetworkSegment(name=name, cidr=cidr, required_hosts=requested[name]))
        cursor += block_size

    return NetworkProfile(cidr_mode=cidr_mode, segments=segments)


def _collect_warnings(host: HostProfile) -> list[str]:
    warnings: list[str] = []
    if host.is_wsl:
        warnings.append(
            "Host is WSL-based. Prefer persistent Docker volumes and explicit "
            "backups over host package assumptions."
        )
    if host.available_memory_bytes < 2 * 1024**3:
        warnings.append(
            "Available memory is below 2 GiB. Keep NetBox workers at 1 and "
            "avoid enabling optional heavy integrations."
        )
    if not host.docker_capable:
        warnings.append(
            "Report did not confirm Docker control capability. The generated "
            "compose bundle has not been tailored for runtime execution on "
            "this host."
        )
    warnings.append(
        "The Proxmox plugin (netbox-proxbox) is included in the plugin spec "
        "list but disabled because the current release (0.0.6b2) declares "
        "max_version='4.2.99', which is incompatible with the pinned NetBox "
        "4.5.x image. To enable Proxmox inventory sync, wait for an officially "
        "supported netbox-proxbox release targeting NetBox 4.5, or use the "
        "NetBox Labs event-driven Proxmox automation solution "
        "(https://github.com/netboxlabs/netbox-proxmox-automation) as a "
        "webhook-based alternative that does not require a plugin."
    )
    warnings.append(
        "The ACL plugin (netbox-acls) is included but disabled because upstream "
        "declares max_version='4.4.99'. Keep it disabled on NetBox 4.5.x until "
        "a compatible release is published."
    )
    warnings.append(
        "The Prometheus discovery plugin (netbox-prometheus-sd) is included "
        "but disabled because version 0.5 still imports the legacy "
        "extras.plugins API and fails on NetBox 4.5.x."
    )
    return warnings


def _collect_notes(track: str) -> list[str]:
    image_defaults = TRACK_IMAGE_DEFAULTS[track]
    return [
        (
            "Deployment follows the official netbox-docker plugin workflow "
            f"baseline pinned to release {NETBOX_DOCKER_WORKFLOW_VERSION}."
        ),
        (
            f"Track '{track}' is tied to "
            f"{image_defaults['release_reference']} for OS lifecycle alignment."
        ),
        (
            "Topology, BGP, and DNS plugins are enabled because they have "
            "current NetBox 4.5 compatibility evidence from official NetBox "
            "Community sources. The DNS plugin (netbox-plugin-dns 1.5.3) "
            "explicitly declares min_version='4.5.0'."
        ),
        (
            "Diode is enabled using netboxlabs-diode-netbox-plugin 1.7.1 "
            "with module netbox_diode_plugin; upstream declares min_version=4.4.10 "
            "and max_version=4.5.99, so it is compatible with the pinned NetBox 4.5.x."
        ),
        (
            "netbox-acls 1.9.1, netbox-proxbox 0.0.6b2, and "
            "netbox-prometheus-sd 0.5 remain disabled by default "
            "because their declared max_version constraints do not include NetBox 4.5.x."
        ),
        (
            "Requested plugins netbox-config-diff 2.14.0, "
            "netbox-floorplan-plugin 0.9.0, and netbox-inventory 2.5.0 are "
            "integrated by default using upstream compatibility metadata."
        ),
        (
            "netbox-reorder-rack 1.1.4 is enabled as a community integration; "
            "validate in staging before production because upstream metadata does "
            "not publish a strict NetBox 4.5 compatibility matrix."
        ),
        (
            "Worker-container orchestration is generated explicitly so RQ workers "
            "can scale as independent containers while preserving a deterministic "
            "startup dependency on NetBox health."
        ),
        (
            "ORB container orchestration metadata is generated under "
            "configuration/orb/orchestration.yml and the orb-agent service is "
            "started in the default compose deployment after NetBox health."
        ),
        (
            "DNS management is provided by netbox-plugin-dns 1.5.3, which "
            "explicitly targets NetBox 4.5.0+ and handles zones, records, "
            "nameservers, and DNSSEC key templates natively inside NetBox."
        ),
        (
            "The Proxmox plugin (netbox-proxbox) is included in the plugin "
            "spec list as a documented integration option but is disabled "
            "because the current release is incompatible with NetBox 4.5. "
            "For event-driven Proxmox automation without a plugin, see the "
            "NetBox Labs netbox-proxmox-automation project."
        ),
        (
            "The NetBox community device-type library is pinned by commit and "
            "imported through NetBox core bulk-import views rather than an external "
            "helper script."
        ),
        (
            "The bootstrap superuser is pseudonymous and intended only for "
            "initial RBAC setup and rotation."
        ),
        (
            "Least privilege is enforced with dropped Linux capabilities and "
            "separated database/bootstrap secret files; the default importer "
            "workflow can be overridden to use a dedicated NetBox user."
        ),
    ]


def build_plan(
    report: dict[str, Any],
    track: str,
    deployment_name: str,
    source_report: Path | str,
    cidr_mode: str = "deterministic",
    required_hosts: dict[str, int] | None = None,
    worker_containers: int | None = None,
) -> DeploymentPlan:
    """Build a deployment plan from a collector report."""

    if track not in TRACK_IMAGE_DEFAULTS:
        expected = ", ".join(sorted(TRACK_IMAGE_DEFAULTS))
        raise ValueError(f"Unsupported track '{track}'. Expected one of: {expected}")

    host = _build_host_profile(report)
    image_defaults = TRACK_IMAGE_DEFAULTS[track]
    sizing = _derive_sizing(host)
    if worker_containers is not None:
        sizing.netbox_worker_containers = max(1, worker_containers)

    return DeploymentPlan(
        deployment_name=deployment_name,
        source_report=str(source_report),
        source_generator_version=report["report_metadata"]["generator_version"],
        host=host,
        sizing=sizing,
        images=ImageSelection(
            netbox_image=NETBOX_IMAGE,
            postgres_image=image_defaults["postgres_image"],
            valkey_image=image_defaults["valkey_image"],
            track=track,
            release_reference=image_defaults["release_reference"],
        ),
        plugins=_select_plugins(),
        networks=_derive_network_profile(cidr_mode=cidr_mode, required_hosts=required_hosts),
        admin_privacy=_derive_admin_privacy(report),
        device_type_library=_derive_device_type_library_profile(),
        warnings=_collect_warnings(host),
        notes=_collect_notes(track),
    )
