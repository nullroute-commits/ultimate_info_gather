"""
Proxmox VE information data model.

Captures Proxmox cluster details, node information, virtual machines,
containers, storage, and network configuration from the Proxmox API
and local system commands.

Based on Proxmox VE API documentation:
https://pve.proxmox.com/pve-docs/api-viewer/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class ProxmoxNodeStatus(Enum):
    """Proxmox node status."""
    ONLINE = auto()
    OFFLINE = auto()
    UNKNOWN = auto()


class VMStatus(Enum):
    """Virtual machine status."""
    RUNNING = auto()
    STOPPED = auto()
    PAUSED = auto()
    SUSPENDED = auto()
    UNKNOWN = auto()


class StorageType(Enum):
    """Proxmox storage type."""
    DIR = auto()
    LVM = auto()
    LVMTHIN = auto()
    ZFS = auto()
    ZFSPOOL = auto()
    NFS = auto()
    CIFS = auto()
    ISCSI = auto()
    CEPH = auto()
    ROOK_CEPH = auto()
    PBS = auto()
    OTHER = auto()


class StorageContentType(Enum):
    """Content types supported by storage."""
    IMAGES = auto()
    ROOTDIR = auto()
    VZTMPL = auto()
    BACKUP = auto()
    ISO = auto()
    SNIPPETS = auto()


@dataclass
class ProxmoxVersion:
    """Proxmox VE version information."""
    version: str
    release: str
    repo_id: str | None
    kernel_version: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "release": self.release,
            "repo_id": self.repo_id,
            "kernel_version": self.kernel_version,
        }


@dataclass
class ProxmoxClusterInfo:
    """Proxmox cluster information."""
    name: str | None
    version: int | None
    nodes_count: int
    quorate: bool | None
    cluster_id: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "version": self.version,
            "nodes_count": self.nodes_count,
            "quorate": self.quorate,
            "cluster_id": self.cluster_id,
        }


@dataclass
class ProxmoxNodeInfo:
    """Proxmox node details."""
    name: str
    status: ProxmoxNodeStatus
    cpu_count: int | None
    cpu_usage_percent: float | None
    memory_total_bytes: int | None
    memory_used_bytes: int | None
    memory_free_bytes: int | None
    swap_total_bytes: int | None
    swap_used_bytes: int | None
    uptime_seconds: int | None
    kernel_version: str | None
    pve_version: str | None
    cpu_model: str | None
    local_disk_total_bytes: int | None
    local_disk_used_bytes: int | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.name,
            "cpu_count": self.cpu_count,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_total_bytes": self.memory_total_bytes,
            "memory_used_bytes": self.memory_used_bytes,
            "memory_free_bytes": self.memory_free_bytes,
            "swap_total_bytes": self.swap_total_bytes,
            "swap_used_bytes": self.swap_used_bytes,
            "uptime_seconds": self.uptime_seconds,
            "kernel_version": self.kernel_version,
            "pve_version": self.pve_version,
            "cpu_model": self.cpu_model,
            "local_disk_total_bytes": self.local_disk_total_bytes,
            "local_disk_used_bytes": self.local_disk_used_bytes,
        }


@dataclass
class ProxmoxVM:
    """Proxmox virtual machine (QEMU) details."""
    vmid: int
    name: str
    status: VMStatus
    node: str
    cpu_cores: int | None
    cpu_usage_percent: float | None
    memory_max_bytes: int | None
    memory_used_bytes: int | None
    disk_total_bytes: int | None
    disk_used_bytes: int | None
    uptime_seconds: int | None
    template: bool
    tags: list[str]
    ha_state: str | None
    agent_running: bool | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vmid": self.vmid,
            "name": self.name,
            "status": self.status.name,
            "node": self.node,
            "cpu_cores": self.cpu_cores,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_max_bytes": self.memory_max_bytes,
            "memory_used_bytes": self.memory_used_bytes,
            "disk_total_bytes": self.disk_total_bytes,
            "disk_used_bytes": self.disk_used_bytes,
            "uptime_seconds": self.uptime_seconds,
            "template": self.template,
            "tags": self.tags,
            "ha_state": self.ha_state,
            "agent_running": self.agent_running,
        }


@dataclass
class ProxmoxContainer:
    """Proxmox LXC container details."""
    vmid: int
    name: str
    status: VMStatus
    node: str
    cpu_cores: int | None
    cpu_usage_percent: float | None
    memory_max_bytes: int | None
    memory_used_bytes: int | None
    disk_total_bytes: int | None
    disk_used_bytes: int | None
    swap_total_bytes: int | None
    swap_used_bytes: int | None
    uptime_seconds: int | None
    template: bool
    tags: list[str]
    ha_state: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vmid": self.vmid,
            "name": self.name,
            "status": self.status.name,
            "node": self.node,
            "cpu_cores": self.cpu_cores,
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_max_bytes": self.memory_max_bytes,
            "memory_used_bytes": self.memory_used_bytes,
            "disk_total_bytes": self.disk_total_bytes,
            "disk_used_bytes": self.disk_used_bytes,
            "swap_total_bytes": self.swap_total_bytes,
            "swap_used_bytes": self.swap_used_bytes,
            "uptime_seconds": self.uptime_seconds,
            "template": self.template,
            "tags": self.tags,
            "ha_state": self.ha_state,
        }


@dataclass
class ProxmoxStorage:
    """Proxmox storage pool details."""
    storage_id: str
    node: str | None
    storage_type: StorageType
    content_types: list[StorageContentType]
    total_bytes: int | None
    used_bytes: int | None
    available_bytes: int | None
    enabled: bool
    shared: bool
    path: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "storage_id": self.storage_id,
            "node": self.node,
            "storage_type": self.storage_type.name,
            "content_types": [ct.name for ct in self.content_types],
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "available_bytes": self.available_bytes,
            "enabled": self.enabled,
            "shared": self.shared,
            "path": self.path,
        }


@dataclass
class ProxmoxNetworkInterface:
    """Proxmox network interface (bridge, bond, vlan, etc.)."""
    iface: str
    interface_type: str  # bridge, bond, eth, vlan, OVSBridge, etc.
    address: str | None
    netmask: str | None
    gateway: str | None
    bridge_ports: str | None
    bond_slaves: str | None
    vlan_id: int | None
    active: bool
    autostart: bool
    comments: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "iface": self.iface,
            "interface_type": self.interface_type,
            "address": self.address,
            "netmask": self.netmask,
            "gateway": self.gateway,
            "bridge_ports": self.bridge_ports,
            "bond_slaves": self.bond_slaves,
            "vlan_id": self.vlan_id,
            "active": self.active,
            "autostart": self.autostart,
            "comments": self.comments,
        }


@dataclass
class ProxmoxInfo:
    """
    Complete Proxmox VE information collection.

    Captures cluster-level and node-level details from a Proxmox VE host.
    """
    timestamp: datetime
    is_proxmox_host: bool

    # Proxmox version
    version: ProxmoxVersion | None

    # Cluster info
    cluster: ProxmoxClusterInfo | None

    # Nodes
    nodes: list[ProxmoxNodeInfo]

    # Virtual machines (QEMU)
    virtual_machines: list[ProxmoxVM]

    # LXC containers
    containers: list[ProxmoxContainer]

    # Storage pools
    storage_pools: list[ProxmoxStorage]

    # Network interfaces (Proxmox-managed)
    network_interfaces: list[ProxmoxNetworkInterface]

    # Summary stats
    total_vms: int = 0
    running_vms: int = 0
    total_containers: int = 0
    running_containers: int = 0
    total_storage_bytes: int = 0
    used_storage_bytes: int = 0

    # Metadata
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "is_proxmox_host": self.is_proxmox_host,
            "version": self.version.to_dict() if self.version else None,
            "cluster": self.cluster.to_dict() if self.cluster else None,
            "nodes": [n.to_dict() for n in self.nodes],
            "virtual_machines": [vm.to_dict() for vm in self.virtual_machines],
            "containers": [ct.to_dict() for ct in self.containers],
            "storage_pools": [s.to_dict() for s in self.storage_pools],
            "network_interfaces": [n.to_dict() for n in self.network_interfaces],
            "total_vms": self.total_vms,
            "running_vms": self.running_vms,
            "total_containers": self.total_containers,
            "running_containers": self.running_containers,
            "total_storage_bytes": self.total_storage_bytes,
            "used_storage_bytes": self.used_storage_bytes,
            "collection_duration_ms": self.collection_duration_ms,
            "errors": self.errors,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            "=" * 60,
            "PROXMOX VE SUMMARY",
            "=" * 60,
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Is Proxmox Host: {self.is_proxmox_host}",
            "",
        ]

        if not self.is_proxmox_host:
            lines.append("This system is not a Proxmox VE host.")
            lines.append("=" * 60)
            return "\n".join(lines)

        if self.version:
            lines.extend([
                "Version:",
                f"  PVE Version: {self.version.version}",
                f"  Release: {self.version.release}",
                "",
            ])

        if self.cluster:
            lines.extend([
                "Cluster:",
                f"  Name: {self.cluster.name or 'N/A'}",
                f"  Nodes: {self.cluster.nodes_count}",
                f"  Quorate: {self.cluster.quorate}",
                "",
            ])

        lines.extend([
            "Nodes:",
        ])
        for node in self.nodes:
            status = node.status.name
            cpu_pct = f"{node.cpu_usage_percent:.1f}%" if node.cpu_usage_percent else "N/A"
            mem_used = ""
            if node.memory_total_bytes and node.memory_used_bytes:
                mem_pct = (node.memory_used_bytes / node.memory_total_bytes) * 100
                mem_used = f"{mem_pct:.1f}%"
            lines.append(f"  {node.name}: {status} (CPU: {cpu_pct}, Mem: {mem_used})")
        lines.append("")

        lines.extend([
            "Workloads:",
            f"  VMs: {self.running_vms}/{self.total_vms} running",
            f"  Containers: {self.running_containers}/{self.total_containers} running",
            "",
        ])

        if self.storage_pools:
            total_gb = self.total_storage_bytes / (1024**3) if self.total_storage_bytes else 0
            used_gb = self.used_storage_bytes / (1024**3) if self.used_storage_bytes else 0
            lines.extend([
                "Storage:",
                f"  Pools: {len(self.storage_pools)}",
                f"  Total: {total_gb:.2f} GB",
                f"  Used: {used_gb:.2f} GB",
                "",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)
