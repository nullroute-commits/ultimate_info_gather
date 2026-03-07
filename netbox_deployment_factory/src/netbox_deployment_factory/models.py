"""Typed models for deployment planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class HostProfile:
    """Host capabilities derived from an ultimate_info_gather report."""

    hostname: str
    operating_system: str
    operating_system_version: str
    kernel_version: str
    architecture: str
    is_wsl: bool
    is_virtual_machine: bool
    hypervisor: str | None
    docker_capable: bool
    can_install_packages: bool
    total_memory_bytes: int
    available_memory_bytes: int
    logical_cores: int
    default_gateway: str | None
    nameservers: list[str]


@dataclass(slots=True)
class PluginSpec:
    """A NetBox plugin selection."""

    package_name: str
    module_name: str
    version: str
    enabled: bool
    support_tier: str
    rationale: str
    install_when_disabled: bool = False
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ServiceSizing:
    """Sizing decisions for the generated deployment."""

    profile_name: str
    netbox_workers: int
    netbox_worker_containers: int
    postgres_shared_buffers: str
    postgres_max_connections: int
    housekeeping_interval_minutes: int


@dataclass(slots=True)
class ImageSelection:
    """Pinned image decisions."""

    netbox_image: str
    postgres_image: str
    valkey_image: str
    track: str
    release_reference: str


@dataclass(slots=True)
class AdminPrivacyProfile:
    """Anonymous bootstrap admin configuration."""

    bootstrap_username: str
    bootstrap_email: str
    bootstrap_secret_files: list[str]
    rotation_required: bool
    rationale: str


@dataclass(slots=True)
class DeviceTypeLibraryProfile:
    """Pinned NetBox community device-type library import profile."""

    library_repository: str
    library_ref: str
    import_service_name: str
    vendor_filter_env_var: str
    rationale: str
    least_privilege_permissions: list[str]


@dataclass(slots=True)
class NetworkSegment:
    """A single scoped Docker network segment."""

    name: str
    cidr: str
    required_hosts: int


@dataclass(slots=True)
class NetworkProfile:
    """Network planning inputs and computed segment allocations."""

    cidr_mode: str
    segments: list[NetworkSegment]


@dataclass(slots=True)
class DeploymentPlan:
    """Complete deployment plan used by the renderers."""

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
    warnings: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert the plan to plain dictionaries."""

        return asdict(self)
