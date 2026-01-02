"""
Hardware information data model.

Captures comprehensive hardware details and access levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class DeviceType(Enum):
    """Hardware device type classification."""
    CPU = auto()
    MEMORY = auto()
    STORAGE = auto()
    NETWORK = auto()
    GPU = auto()
    USB = auto()
    PCI = auto()
    AUDIO = auto()
    INPUT = auto()
    DISPLAY = auto()
    OTHER = auto()


class DeviceAccessLevel(Enum):
    """Access level for a hardware device."""
    NONE = auto()
    READ_ONLY = auto()
    READ_WRITE = auto()
    EXCLUSIVE = auto()
    SHARED = auto()
    BLOCKED = auto()


@dataclass
class CPUInfo:
    """CPU hardware information."""
    model_name: str
    vendor: str
    architecture: str
    physical_cores: int
    logical_cores: int
    max_frequency_mhz: float | None
    current_frequency_mhz: float | None
    cache_size_kb: dict[str, int]  # L1, L2, L3
    flags: list[str]
    virtualization_supported: bool
    is_hypervisor: bool
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "vendor": self.vendor,
            "architecture": self.architecture,
            "physical_cores": self.physical_cores,
            "logical_cores": self.logical_cores,
            "max_frequency_mhz": self.max_frequency_mhz,
            "current_frequency_mhz": self.current_frequency_mhz,
            "cache_size_kb": self.cache_size_kb,
            "flags": self.flags,
            "virtualization_supported": self.virtualization_supported,
            "is_hypervisor": self.is_hypervisor,
        }


@dataclass
class MemoryInfo:
    """Memory hardware information."""
    total_bytes: int
    available_bytes: int
    used_bytes: int
    percent_used: float
    swap_total_bytes: int
    swap_used_bytes: int
    swap_free_bytes: int
    memory_type: str | None  # DDR4, DDR5, etc.
    speed_mhz: int | None
    slots_used: int | None
    slots_total: int | None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_bytes": self.total_bytes,
            "available_bytes": self.available_bytes,
            "used_bytes": self.used_bytes,
            "percent_used": self.percent_used,
            "swap_total_bytes": self.swap_total_bytes,
            "swap_used_bytes": self.swap_used_bytes,
            "swap_free_bytes": self.swap_free_bytes,
            "memory_type": self.memory_type,
            "speed_mhz": self.speed_mhz,
            "slots_used": self.slots_used,
            "slots_total": self.slots_total,
        }


@dataclass
class StorageDevice:
    """Storage device information."""
    device_path: str
    name: str
    model: str | None
    serial: str | None
    size_bytes: int
    type: str  # HDD, SSD, NVMe, etc.
    is_removable: bool
    partitions: list[dict[str, Any]]
    mount_points: list[str]
    filesystem: str | None
    access_level: DeviceAccessLevel
    is_system_disk: bool
    smart_status: str | None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_path": self.device_path,
            "name": self.name,
            "model": self.model,
            "serial": self.serial,
            "size_bytes": self.size_bytes,
            "type": self.type,
            "is_removable": self.is_removable,
            "partitions": self.partitions,
            "mount_points": self.mount_points,
            "filesystem": self.filesystem,
            "access_level": self.access_level.name,
            "is_system_disk": self.is_system_disk,
            "smart_status": self.smart_status,
        }


@dataclass
class NetworkInterface:
    """Network interface information."""
    name: str
    mac_address: str | None
    ipv4_addresses: list[str]
    ipv6_addresses: list[str]
    is_up: bool
    is_loopback: bool
    is_virtual: bool
    speed_mbps: int | None
    mtu: int
    driver: str | None
    access_level: DeviceAccessLevel
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "mac_address": self.mac_address,
            "ipv4_addresses": self.ipv4_addresses,
            "ipv6_addresses": self.ipv6_addresses,
            "is_up": self.is_up,
            "is_loopback": self.is_loopback,
            "is_virtual": self.is_virtual,
            "speed_mbps": self.speed_mbps,
            "mtu": self.mtu,
            "driver": self.driver,
            "access_level": self.access_level.name,
        }


@dataclass
class GPUInfo:
    """GPU hardware information."""
    name: str
    vendor: str
    driver: str | None
    driver_version: str | None
    memory_total_bytes: int | None
    memory_used_bytes: int | None
    pci_bus_id: str | None
    is_integrated: bool
    compute_capability: str | None  # For CUDA
    access_level: DeviceAccessLevel
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "vendor": self.vendor,
            "driver": self.driver,
            "driver_version": self.driver_version,
            "memory_total_bytes": self.memory_total_bytes,
            "memory_used_bytes": self.memory_used_bytes,
            "pci_bus_id": self.pci_bus_id,
            "is_integrated": self.is_integrated,
            "compute_capability": self.compute_capability,
            "access_level": self.access_level.name,
        }


@dataclass 
class USBDevice:
    """USB device information."""
    bus: int
    device: int
    vendor_id: str
    product_id: str
    vendor_name: str | None
    product_name: str | None
    device_class: str
    serial: str | None
    access_level: DeviceAccessLevel
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bus": self.bus,
            "device": self.device,
            "vendor_id": self.vendor_id,
            "product_id": self.product_id,
            "vendor_name": self.vendor_name,
            "product_name": self.product_name,
            "device_class": self.device_class,
            "serial": self.serial,
            "access_level": self.access_level.name,
        }


@dataclass
class SystemBoardInfo:
    """Motherboard/System board information."""
    manufacturer: str | None
    product_name: str | None
    version: str | None
    serial: str | None
    bios_vendor: str | None
    bios_version: str | None
    bios_date: str | None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "manufacturer": self.manufacturer,
            "product_name": self.product_name,
            "version": self.version,
            "serial": self.serial,
            "bios_vendor": self.bios_vendor,
            "bios_version": self.bios_version,
            "bios_date": self.bios_date,
        }


@dataclass
class HardwareInfo:
    """
    Complete hardware information collection.
    
    Comprehensive hardware inventory with access level information.
    """
    timestamp: datetime
    
    # System identification
    system_board: SystemBoardInfo | None
    machine_id: str | None
    product_uuid: str | None
    
    # Core hardware
    cpu: CPUInfo | None
    memory: MemoryInfo | None
    
    # Storage
    storage_devices: list[StorageDevice]
    
    # Network
    network_interfaces: list[NetworkInterface]
    
    # Graphics
    gpus: list[GPUInfo]
    
    # Peripherals
    usb_devices: list[USBDevice]
    
    # Device access summary
    device_access_summary: dict[str, DeviceAccessLevel]
    
    # Virtualization
    is_virtual_machine: bool
    hypervisor: str | None
    vm_type: str | None
    
    # Metadata
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "system_board": self.system_board.to_dict() if self.system_board else None,
            "machine_id": self.machine_id,
            "product_uuid": self.product_uuid,
            "cpu": self.cpu.to_dict() if self.cpu else None,
            "memory": self.memory.to_dict() if self.memory else None,
            "storage_devices": [d.to_dict() for d in self.storage_devices],
            "network_interfaces": [n.to_dict() for n in self.network_interfaces],
            "gpus": [g.to_dict() for g in self.gpus],
            "usb_devices": [u.to_dict() for u in self.usb_devices],
            "device_access_summary": {k: v.name for k, v in self.device_access_summary.items()},
            "is_virtual_machine": self.is_virtual_machine,
            "hypervisor": self.hypervisor,
            "vm_type": self.vm_type,
            "collection_duration_ms": self.collection_duration_ms,
            "errors": self.errors,
        }
    
    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            "=" * 60,
            "HARDWARE SUMMARY",
            "=" * 60,
            f"Timestamp: {self.timestamp.isoformat()}",
            "",
        ]
        
        if self.cpu:
            lines.extend([
                "CPU:",
                f"  Model: {self.cpu.model_name}",
                f"  Architecture: {self.cpu.architecture}",
                f"  Cores: {self.cpu.physical_cores} physical, {self.cpu.logical_cores} logical",
                f"  Virtualization: {self.cpu.virtualization_supported}",
                "",
            ])
        
        if self.memory:
            total_gb = self.memory.total_bytes / (1024**3)
            avail_gb = self.memory.available_bytes / (1024**3)
            lines.extend([
                "Memory:",
                f"  Total: {total_gb:.2f} GB",
                f"  Available: {avail_gb:.2f} GB",
                f"  Used: {self.memory.percent_used:.1f}%",
                "",
            ])
        
        lines.extend([
            f"Storage Devices: {len(self.storage_devices)}",
            f"Network Interfaces: {len(self.network_interfaces)}",
            f"GPUs: {len(self.gpus)}",
            f"USB Devices: {len(self.usb_devices)}",
            "",
            f"Virtual Machine: {self.is_virtual_machine}",
        ])
        
        if self.is_virtual_machine and self.hypervisor:
            lines.append(f"Hypervisor: {self.hypervisor}")
        
        lines.append("=" * 60)
        return "\n".join(lines)
