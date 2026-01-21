"""
Permissions and resource data models.

Captures permission levels and available resources for the running process.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class PermissionLevel(Enum):
    """Process permission level classification."""
    ROOT = auto()          # Full system access
    SUDO = auto()          # Can elevate to root
    PRIVILEGED = auto()    # Part of privileged groups
    STANDARD = auto()      # Normal user permissions
    RESTRICTED = auto()    # Limited permissions
    SANDBOXED = auto()     # Heavily restricted
    UNKNOWN = auto()


class AccessLevel(Enum):
    """Access level for a resource."""
    NONE = auto()
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    READ_WRITE = auto()
    READ_EXECUTE = auto()
    WRITE_EXECUTE = auto()
    FULL = auto()


@dataclass
class GroupInfo:
    """User group information."""
    gid: int
    name: str
    is_privileged: bool = False

    # Well-known privileged groups
    PRIVILEGED_GROUPS = frozenset({
        'root', 'wheel', 'sudo', 'admin', 'adm',
        'docker', 'lxd', 'libvirt', 'kvm',
        'disk', 'sys', 'shadow',
    })

    @classmethod
    def from_gid(cls, gid: int, name: str) -> GroupInfo:
        """Create GroupInfo from gid and name."""
        return cls(
            gid=gid,
            name=name,
            is_privileged=name in cls.PRIVILEGED_GROUPS,
        )


@dataclass
class FileSystemPermission:
    """File system permission check result."""
    path: str
    exists: bool
    readable: bool
    writable: bool
    executable: bool
    is_directory: bool
    owner_uid: int | None = None
    owner_gid: int | None = None
    mode: int | None = None

    @property
    def access_level(self) -> AccessLevel:
        """Determine access level."""
        if not self.exists:
            return AccessLevel.NONE

        r, w, x = self.readable, self.writable, self.executable

        if r and w and x:
            return AccessLevel.FULL
        if r and w:
            return AccessLevel.READ_WRITE
        if r and x:
            return AccessLevel.READ_EXECUTE
        if w and x:
            return AccessLevel.WRITE_EXECUTE
        if r:
            return AccessLevel.READ
        if w:
            return AccessLevel.WRITE
        if x:
            return AccessLevel.EXECUTE
        return AccessLevel.NONE


@dataclass
class CapabilityInfo:
    """Linux capability information."""
    name: str
    effective: bool
    permitted: bool
    inheritable: bool


@dataclass
class ResourceLimits:
    """Process resource limits (ulimits)."""
    max_open_files: tuple[int, int] | None = None  # (soft, hard)
    max_processes: tuple[int, int] | None = None
    max_memory: tuple[int, int] | None = None
    max_stack_size: tuple[int, int] | None = None
    max_cpu_time: tuple[int, int] | None = None
    max_file_size: tuple[int, int] | None = None
    max_core_size: tuple[int, int] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_open_files": self.max_open_files,
            "max_processes": self.max_processes,
            "max_memory": self.max_memory,
            "max_stack_size": self.max_stack_size,
            "max_cpu_time": self.max_cpu_time,
            "max_file_size": self.max_file_size,
            "max_core_size": self.max_core_size,
        }


@dataclass
class ResourceInfo:
    """Available system resources."""
    cpu_count: int
    cpu_count_logical: int
    memory_total_bytes: int
    memory_available_bytes: int
    disk_partitions: list[dict[str, Any]]
    network_interfaces: list[str]
    resource_limits: ResourceLimits

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cpu_count": self.cpu_count,
            "cpu_count_logical": self.cpu_count_logical,
            "memory_total_bytes": self.memory_total_bytes,
            "memory_available_bytes": self.memory_available_bytes,
            "disk_partitions": self.disk_partitions,
            "network_interfaces": self.network_interfaces,
            "resource_limits": self.resource_limits.to_dict(),
        }


@dataclass
class PermissionsInfo:
    """
    Complete permissions and access information.

    Stores comprehensive information about process permissions,
    capabilities, group memberships, and resource access levels.
    """
    timestamp: datetime
    permission_level: PermissionLevel
    user_id: int | None
    user_name: str | None
    effective_user_id: int | None
    groups: list[GroupInfo]
    privileged_groups: list[str]

    # Capabilities (Linux-specific)
    capabilities: list[CapabilityInfo]
    has_cap_sys_admin: bool
    has_cap_net_admin: bool
    has_cap_dac_override: bool

    # File system access
    fs_permissions: dict[str, FileSystemPermission]

    # Security context
    selinux_enabled: bool
    selinux_context: str | None
    apparmor_enabled: bool
    apparmor_profile: str | None

    # Sudo capabilities
    can_sudo: bool
    sudo_nopasswd: bool

    # Available resources
    resources: ResourceInfo | None

    # Metadata
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "permission_level": self.permission_level.name,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "effective_user_id": self.effective_user_id,
            "groups": [{"gid": g.gid, "name": g.name, "privileged": g.is_privileged} for g in self.groups],
            "privileged_groups": self.privileged_groups,
            "capabilities": [
                {"name": c.name, "effective": c.effective, "permitted": c.permitted, "inheritable": c.inheritable}
                for c in self.capabilities
            ],
            "has_cap_sys_admin": self.has_cap_sys_admin,
            "has_cap_net_admin": self.has_cap_net_admin,
            "has_cap_dac_override": self.has_cap_dac_override,
            "fs_permissions": {
                path: {
                    "exists": p.exists,
                    "readable": p.readable,
                    "writable": p.writable,
                    "executable": p.executable,
                    "access_level": p.access_level.name,
                }
                for path, p in self.fs_permissions.items()
            },
            "selinux_enabled": self.selinux_enabled,
            "selinux_context": self.selinux_context,
            "apparmor_enabled": self.apparmor_enabled,
            "apparmor_profile": self.apparmor_profile,
            "can_sudo": self.can_sudo,
            "sudo_nopasswd": self.sudo_nopasswd,
            "resources": self.resources.to_dict() if self.resources else None,
            "collection_duration_ms": self.collection_duration_ms,
            "errors": self.errors,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            "=" * 60,
            "PERMISSIONS SUMMARY",
            "=" * 60,
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Permission Level: {self.permission_level.name}",
            f"User: {self.user_name} (UID: {self.user_id})",
            f"Effective UID: {self.effective_user_id}",
            "",
            f"Groups ({len(self.groups)}):",
        ]

        for group in self.groups[:10]:  # Limit display
            priv_marker = " [PRIVILEGED]" if group.is_privileged else ""
            lines.append(f"  - {group.name} (GID: {group.gid}){priv_marker}")

        if len(self.groups) > 10:
            lines.append(f"  ... and {len(self.groups) - 10} more")

        lines.extend([
            "",
            "Capabilities:",
            f"  CAP_SYS_ADMIN: {self.has_cap_sys_admin}",
            f"  CAP_NET_ADMIN: {self.has_cap_net_admin}",
            f"  CAP_DAC_OVERRIDE: {self.has_cap_dac_override}",
            "",
            "Security:",
            f"  SELinux: {'Enabled' if self.selinux_enabled else 'Disabled'}",
            f"  AppArmor: {'Enabled' if self.apparmor_enabled else 'Disabled'}",
            f"  Can Sudo: {self.can_sudo}",
            f"  Sudo NOPASSWD: {self.sudo_nopasswd}",
            "",
            "Key Path Access:",
        ])

        for path, perm in list(self.fs_permissions.items())[:5]:
            lines.append(f"  {path}: {perm.access_level.name}")

        lines.append("=" * 60)
        return "\n".join(lines)
