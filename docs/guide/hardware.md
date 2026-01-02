# Hardware Scanning

The hardware collector inventories system hardware components.

## HardwareInfo Model

```python
@dataclass
class HardwareInfo:
    timestamp: datetime
    system_board: SystemBoardInfo | None
    machine_id: str | None
    product_uuid: str | None
    cpu: CPUInfo | None
    memory: MemoryInfo | None
    storage_devices: list[StorageDevice]
    network_interfaces: list[NetworkInterface]
    gpus: list[GPUInfo]
    usb_devices: list[USBDevice]
    device_access_summary: dict[str, DeviceAccessLevel]
    is_virtual_machine: bool
    hypervisor: str | None
    vm_type: str | None
```

## CPU Information

| Field | Description |
|-------|-------------|
| `model_name` | CPU model string |
| `vendor` | Vendor ID (Intel, AMD) |
| `architecture` | x86_64, aarch64, etc. |
| `physical_cores` | Physical core count |
| `logical_cores` | Logical core count (with HT) |
| `max_frequency_mhz` | Maximum frequency |
| `current_frequency_mhz` | Current frequency |
| `cache_size_kb` | L1, L2, L3 cache sizes |
| `flags` | CPU feature flags |
| `virtualization_supported` | VMX/SVM available |
| `is_hypervisor` | Running as hypervisor |

## Memory Information

| Field | Description |
|-------|-------------|
| `total_bytes` | Total physical memory |
| `available_bytes` | Available memory |
| `used_bytes` | Used memory |
| `percent_used` | Usage percentage |
| `swap_total_bytes` | Total swap space |
| `swap_used_bytes` | Used swap |
| `swap_free_bytes` | Free swap |

## Storage Devices

| Field | Description |
|-------|-------------|
| `device_path` | `/dev/sdX` path |
| `name` | Device name |
| `model` | Drive model |
| `size_bytes` | Capacity |
| `type` | HDD, SSD, NVMe |
| `is_removable` | Removable media |
| `partitions` | Partition list |
| `mount_points` | Where mounted |
| `access_level` | R/W access |
| `is_system_disk` | Contains OS |

## Network Interfaces

| Field | Description |
|-------|-------------|
| `name` | Interface name (eth0, etc.) |
| `mac_address` | Hardware address |
| `ipv4_addresses` | IPv4 addresses |
| `ipv6_addresses` | IPv6 addresses |
| `is_up` | Operational state |
| `is_loopback` | Loopback interface |
| `is_virtual` | Virtual interface |
| `speed_mbps` | Link speed |
| `mtu` | MTU size |

## GPU Information

Supports NVIDIA, AMD, and Intel GPUs:

| Field | Description |
|-------|-------------|
| `name` | GPU model name |
| `vendor` | NVIDIA, AMD, Intel |
| `driver` | Driver in use |
| `driver_version` | Driver version |
| `memory_total_bytes` | VRAM total |
| `memory_used_bytes` | VRAM used |
| `pci_bus_id` | PCI bus address |
| `is_integrated` | Integrated GPU |

## Virtualization Detection

Detects virtual machine environments:

| Type | Detection Method |
|------|------------------|
| VMware | DMI, hypervisor flag |
| VirtualBox | DMI, hypervisor flag |
| KVM/QEMU | DMI, cpuid |
| Hyper-V | DMI, hypervisor flag |
| Xen | DMI, xenfs |

## Usage Example

```python
from src.collectors import HardwareCollector

async def scan_hardware():
    collector = HardwareCollector()
    result = await collector.safe_collect()
    
    if result.success:
        hw = result.data
        
        if hw.cpu:
            print(f"CPU: {hw.cpu.model_name}")
            print(f"Cores: {hw.cpu.physical_cores} physical, {hw.cpu.logical_cores} logical")
        
        if hw.memory:
            gb = hw.memory.total_bytes / (1024**3)
            print(f"Memory: {gb:.2f} GB")
        
        print(f"\nStorage Devices: {len(hw.storage_devices)}")
        for dev in hw.storage_devices:
            size_gb = dev.size_bytes / (1024**3)
            print(f"  - {dev.name}: {size_gb:.0f} GB ({dev.type})")
        
        print(f"\nGPUs: {len(hw.gpus)}")
        for gpu in hw.gpus:
            print(f"  - {gpu.vendor}: {gpu.name}")
        
        print(f"\nVirtual Machine: {hw.is_virtual_machine}")
        if hw.hypervisor:
            print(f"Hypervisor: {hw.hypervisor}")
```
