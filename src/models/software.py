"""
Software information data model.

Captures comprehensive software deployment and access levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class SoftwareType(Enum):
    """Software type classification."""
    SYSTEM = auto()
    APPLICATION = auto()
    LIBRARY = auto()
    DRIVER = auto()
    SERVICE = auto()
    CONTAINER = auto()
    PYTHON_PACKAGE = auto()
    KERNEL_MODULE = auto()


class ServiceState(Enum):
    """Service running state."""
    RUNNING = auto()
    STOPPED = auto()
    FAILED = auto()
    INACTIVE = auto()
    UNKNOWN = auto()


@dataclass
class InstalledPackage:
    """Installed system package information."""
    name: str
    version: str
    architecture: str | None
    description: str | None
    installed_size_bytes: int | None
    package_manager: str  # apt, yum, pacman, etc.
    install_date: datetime | None
    is_automatic: bool  # Installed as dependency

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "architecture": self.architecture,
            "description": self.description,
            "installed_size_bytes": self.installed_size_bytes,
            "package_manager": self.package_manager,
            "install_date": self.install_date.isoformat() if self.install_date else None,
            "is_automatic": self.is_automatic,
        }


@dataclass
class PythonPackage:
    """Installed Python package information."""
    name: str
    version: str
    location: str
    requires: list[str]
    required_by: list[str]
    is_editable: bool
    metadata_version: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "location": self.location,
            "requires": self.requires,
            "required_by": self.required_by,
            "is_editable": self.is_editable,
            "metadata_version": self.metadata_version,
        }


@dataclass
class SystemService:
    """System service information."""
    name: str
    display_name: str | None
    description: str | None
    state: ServiceState
    is_enabled: bool
    pid: int | None
    user: str | None
    start_time: datetime | None
    memory_bytes: int | None
    cpu_percent: float | None
    service_type: str | None  # systemd, init, etc.
    can_control: bool  # Can the process start/stop this service

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "state": self.state.name,
            "is_enabled": self.is_enabled,
            "pid": self.pid,
            "user": self.user,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "memory_bytes": self.memory_bytes,
            "cpu_percent": self.cpu_percent,
            "service_type": self.service_type,
            "can_control": self.can_control,
        }


@dataclass
class KernelModule:
    """Loaded kernel module information."""
    name: str
    size_bytes: int
    used_by: list[str]
    state: str  # Live, Loading, Unloading

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "used_by": self.used_by,
            "state": self.state,
        }


@dataclass
class ContainerInfo:
    """Running container information."""
    id: str
    name: str
    image: str
    status: str
    created: datetime | None
    ports: list[dict[str, Any]]
    networks: list[str]
    volumes: list[str]
    runtime: str  # docker, podman, containerd
    can_control: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "image": self.image,
            "status": self.status,
            "created": self.created.isoformat() if self.created else None,
            "ports": self.ports,
            "networks": self.networks,
            "volumes": self.volumes,
            "runtime": self.runtime,
            "can_control": self.can_control,
        }


@dataclass
class RunningProcess:
    """Running process information."""
    pid: int
    name: str
    cmdline: list[str]
    user: str
    status: str
    cpu_percent: float
    memory_percent: float
    memory_bytes: int
    num_threads: int
    create_time: datetime | None
    cwd: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pid": self.pid,
            "name": self.name,
            "cmdline": self.cmdline,
            "user": self.user,
            "status": self.status,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_bytes": self.memory_bytes,
            "num_threads": self.num_threads,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "cwd": self.cwd,
        }


@dataclass
class OSInfo:
    """Operating system information."""
    name: str
    version: str
    release: str
    codename: str | None
    kernel_version: str
    architecture: str
    boot_time: datetime | None
    uptime_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "release": self.release,
            "codename": self.codename,
            "kernel_version": self.kernel_version,
            "architecture": self.architecture,
            "boot_time": self.boot_time.isoformat() if self.boot_time else None,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class SoftwareInfo:
    """
    Complete software information collection.

    Comprehensive software inventory with access level information.
    """
    timestamp: datetime

    # Operating system
    os_info: OSInfo | None

    # Kernel modules
    kernel_modules: list[KernelModule]

    # System packages
    installed_packages: list[InstalledPackage]
    package_managers_available: list[str]

    # Python environment
    python_packages: list[PythonPackage]
    python_version: str
    pip_version: str | None
    virtual_env_active: bool
    virtual_env_path: str | None

    # Services
    system_services: list[SystemService]
    init_system: str | None  # systemd, init, upstart, etc.

    # Containers
    containers: list[ContainerInfo]
    container_runtimes: list[str]

    # Running processes
    running_processes: list[RunningProcess]
    process_count: int

    # Environment
    environment_variables: dict[str, str]
    path_directories: list[str]

    # Access summary
    can_install_packages: bool
    can_manage_services: bool
    can_load_modules: bool
    can_manage_containers: bool

    # Metadata
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "os_info": self.os_info.to_dict() if self.os_info else None,
            "kernel_modules": [m.to_dict() for m in self.kernel_modules],
            "installed_packages_count": len(self.installed_packages),
            "installed_packages": [p.to_dict() for p in self.installed_packages],
            "package_managers_available": self.package_managers_available,
            "python_packages": [p.to_dict() for p in self.python_packages],
            "python_version": self.python_version,
            "pip_version": self.pip_version,
            "virtual_env_active": self.virtual_env_active,
            "virtual_env_path": self.virtual_env_path,
            "system_services_count": len(self.system_services),
            "system_services": [s.to_dict() for s in self.system_services],
            "init_system": self.init_system,
            "containers": [c.to_dict() for c in self.containers],
            "container_runtimes": self.container_runtimes,
            "process_count": self.process_count,
            "running_processes": [p.to_dict() for p in self.running_processes],
            "environment_variables": self.environment_variables,
            "path_directories": self.path_directories,
            "can_install_packages": self.can_install_packages,
            "can_manage_services": self.can_manage_services,
            "can_load_modules": self.can_load_modules,
            "can_manage_containers": self.can_manage_containers,
            "collection_duration_ms": self.collection_duration_ms,
            "errors": self.errors,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            "=" * 60,
            "SOFTWARE SUMMARY",
            "=" * 60,
            f"Timestamp: {self.timestamp.isoformat()}",
            "",
        ]

        if self.os_info:
            lines.extend([
                "Operating System:",
                f"  Name: {self.os_info.name}",
                f"  Version: {self.os_info.version}",
                f"  Kernel: {self.os_info.kernel_version}",
                f"  Architecture: {self.os_info.architecture}",
                f"  Uptime: {self.os_info.uptime_seconds / 3600:.1f} hours",
                "",
            ])

        lines.extend([
            "Package Management:",
            f"  Package Managers: {', '.join(self.package_managers_available) or 'None detected'}",
            f"  Installed Packages: {len(self.installed_packages)}",
            f"  Can Install: {self.can_install_packages}",
            "",
            "Python Environment:",
            f"  Python Version: {self.python_version}",
            f"  Pip Version: {self.pip_version}",
            f"  Virtual Env: {self.virtual_env_active}",
            f"  Python Packages: {len(self.python_packages)}",
            "",
            "Services:",
            f"  Init System: {self.init_system}",
            f"  Total Services: {len(self.system_services)}",
            f"  Can Manage: {self.can_manage_services}",
            "",
            "Containers:",
            f"  Runtimes: {', '.join(self.container_runtimes) or 'None'}",
            f"  Running Containers: {len(self.containers)}",
            f"  Can Manage: {self.can_manage_containers}",
            "",
            "Processes:",
            f"  Total Count: {self.process_count}",
            "",
            "Kernel:",
            f"  Loaded Modules: {len(self.kernel_modules)}",
            f"  Can Load Modules: {self.can_load_modules}",
            "=" * 60,
        ])

        return "\n".join(lines)
