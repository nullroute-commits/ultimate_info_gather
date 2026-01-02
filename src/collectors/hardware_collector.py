"""
Hardware collector - Objective 3 (Part 1).

Collects hardware information and determines access levels.
"""

from __future__ import annotations

import os
import platform
import re
from datetime import datetime
from pathlib import Path

from ..models.environment import EnvironmentState
from ..models.hardware import (
    CPUInfo,
    DeviceAccessLevel,
    GPUInfo,
    HardwareInfo,
    MemoryInfo,
    NetworkInterface,
    StorageDevice,
    SystemBoardInfo,
    USBDevice,
)
from ..models.permissions import PermissionsInfo
from .base import BaseCollector


class HardwareCollector(BaseCollector[HardwareInfo]):
    """
    Collects comprehensive hardware information.
    
    Objective 3: Collect all hardware deployed and determine access levels.
    """

    def __init__(
        self,
        environment_state: EnvironmentState | None = None,
        permissions_info: PermissionsInfo | None = None,
    ):
        """
        Initialize with optional prior collection results.
        
        Args:
            environment_state: Previously collected environment info
            permissions_info: Previously collected permissions info
        """
        super().__init__()
        self.env_state = environment_state
        self.perm_info = permissions_info

    async def collect(self) -> HardwareInfo:
        """Collect hardware information."""
        timestamp = datetime.now()

        # Collect all hardware info in parallel where possible
        (
            system_board,
            machine_id,
            product_uuid,
            cpu_info,
            memory_info,
            storage_devices,
            network_interfaces,
            gpus,
            usb_devices,
            vm_info,
        ) = await self.gather_with_errors(
            self._get_system_board(),
            self._get_machine_id(),
            self._get_product_uuid(),
            self._get_cpu_info(),
            self._get_memory_info(),
            self._get_storage_devices(),
            self._get_network_interfaces(),
            self._get_gpu_info(),
            self._get_usb_devices(),
            self._check_virtualization(),
        )

        # Build device access summary
        device_access_summary = await self._build_access_summary(
            storage_devices or [],
            network_interfaces or [],
            gpus or [],
            usb_devices or [],
        )

        is_vm, hypervisor, vm_type = vm_info if vm_info else (False, None, None)

        return HardwareInfo(
            timestamp=timestamp,
            system_board=system_board,
            machine_id=machine_id,
            product_uuid=product_uuid,
            cpu=cpu_info,
            memory=memory_info,
            storage_devices=storage_devices or [],
            network_interfaces=network_interfaces or [],
            gpus=gpus or [],
            usb_devices=usb_devices or [],
            device_access_summary=device_access_summary,
            is_virtual_machine=is_vm,
            hypervisor=hypervisor,
            vm_type=vm_type,
            errors=self._errors.copy(),
        )

    async def _get_system_board(self) -> SystemBoardInfo | None:
        """Get motherboard/system board information."""
        try:
            dmi_path = Path('/sys/class/dmi/id')

            if not dmi_path.exists():
                return None

            manufacturer = await self.read_file_async(str(dmi_path / 'board_vendor'))
            product = await self.read_file_async(str(dmi_path / 'board_name'))
            version = await self.read_file_async(str(dmi_path / 'board_version'))
            serial = await self.read_file_async(str(dmi_path / 'board_serial'))
            bios_vendor = await self.read_file_async(str(dmi_path / 'bios_vendor'))
            bios_version = await self.read_file_async(str(dmi_path / 'bios_version'))
            bios_date = await self.read_file_async(str(dmi_path / 'bios_date'))

            return SystemBoardInfo(
                manufacturer=manufacturer.strip() if manufacturer else None,
                product_name=product.strip() if product else None,
                version=version.strip() if version else None,
                serial=serial.strip() if serial else None,
                bios_vendor=bios_vendor.strip() if bios_vendor else None,
                bios_version=bios_version.strip() if bios_version else None,
                bios_date=bios_date.strip() if bios_date else None,
            )
        except Exception as e:
            self.add_warning(f"Failed to get system board info: {e}")
            return None

    async def _get_machine_id(self) -> str | None:
        """Get machine ID. Optional on embedded systems."""
        content = await self.read_file_async('/etc/machine-id', silent_if_missing=True)
        return content.strip() if content else None

    async def _get_product_uuid(self) -> str | None:
        """Get product UUID. Not available on ARM/embedded systems."""
        content = await self.read_file_async('/sys/class/dmi/id/product_uuid', silent_if_missing=True)
        return content.strip() if content else None

    async def _get_cpu_info(self) -> CPUInfo | None:
        """Get CPU information."""
        try:
            cpuinfo = await self.read_file_async('/proc/cpuinfo')
            if not cpuinfo:
                return None

            model_name = vendor = ""
            flags: list[str] = []
            physical_ids = set()
            processor_count = 0
            cache_size = {}

            for line in cpuinfo.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()

                    if key == 'model name':
                        model_name = value
                    elif key == 'vendor_id':
                        vendor = value
                    elif key == 'flags':
                        flags = value.split()
                    elif key == 'physical id':
                        physical_ids.add(value)
                    elif key == 'processor':
                        processor_count += 1
                    elif key == 'cache size':
                        cache_size['L2'] = int(value.split()[0])

            # Get cache info from sysfs
            cache_path = Path('/sys/devices/system/cpu/cpu0/cache')
            if cache_path.exists():
                for index_dir in cache_path.iterdir():
                    if index_dir.is_dir():
                        level_file = index_dir / 'level'
                        size_file = index_dir / 'size'
                        if level_file.exists() and size_file.exists():
                            level = (await self.read_file_async(str(level_file)) or '').strip()
                            size = (await self.read_file_async(str(size_file)) or '').strip()
                            if level and size:
                                # Parse size (e.g., "32K" -> 32)
                                size_val = int(re.sub(r'[^\d]', '', size))
                                cache_size[f'L{level}'] = size_val

            # Get frequency info
            max_freq = None
            cur_freq = None
            freq_path = Path('/sys/devices/system/cpu/cpu0/cpufreq')
            if freq_path.exists():
                max_freq_content = await self.read_file_async(str(freq_path / 'cpuinfo_max_freq'))
                cur_freq_content = await self.read_file_async(str(freq_path / 'scaling_cur_freq'))
                if max_freq_content:
                    max_freq = int(max_freq_content.strip()) / 1000  # kHz to MHz
                if cur_freq_content:
                    cur_freq = int(cur_freq_content.strip()) / 1000

            # Check virtualization support
            virt_supported = any(f in flags for f in ['vmx', 'svm'])
            is_hypervisor = 'hypervisor' in flags

            return CPUInfo(
                model_name=model_name,
                vendor=vendor,
                architecture=platform.machine(),
                physical_cores=len(physical_ids) if physical_ids else processor_count,
                logical_cores=processor_count,
                max_frequency_mhz=max_freq,
                current_frequency_mhz=cur_freq,
                cache_size_kb=cache_size,
                flags=flags,
                virtualization_supported=virt_supported,
                is_hypervisor=is_hypervisor,
            )
        except Exception as e:
            self.add_warning(f"Failed to get CPU info: {e}")
            return None

    async def _get_memory_info(self) -> MemoryInfo | None:
        """Get memory information."""
        try:
            meminfo = await self.read_file_async('/proc/meminfo')
            if not meminfo:
                return None

            mem_data: dict[str, int] = {}
            for line in meminfo.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    # Parse value (e.g., "16384 kB" -> 16384)
                    parts = value.strip().split()
                    if parts:
                        mem_data[key] = int(parts[0]) * 1024  # kB to bytes

            total = mem_data.get('MemTotal', 0)
            available = mem_data.get('MemAvailable', 0)
            used = total - available
            percent = (used / total * 100) if total > 0 else 0

            return MemoryInfo(
                total_bytes=total,
                available_bytes=available,
                used_bytes=used,
                percent_used=percent,
                swap_total_bytes=mem_data.get('SwapTotal', 0),
                swap_used_bytes=mem_data.get('SwapTotal', 0) - mem_data.get('SwapFree', 0),
                swap_free_bytes=mem_data.get('SwapFree', 0),
                memory_type=None,  # Requires dmidecode
                speed_mhz=None,
                slots_used=None,
                slots_total=None,
            )
        except Exception as e:
            self.add_warning(f"Failed to get memory info: {e}")
            return None

    async def _get_storage_devices(self) -> list[StorageDevice]:
        """Get storage device information."""
        devices = []

        try:
            block_path = Path('/sys/block')
            if not block_path.exists():
                return devices

            for device_dir in block_path.iterdir():
                name = device_dir.name

                # Skip virtual devices
                if name.startswith(('loop', 'ram', 'dm-')):
                    continue

                device_path = f'/dev/{name}'

                # Get size
                size_file = device_dir / 'size'
                size_bytes = 0
                if size_file.exists():
                    size_content = await self.read_file_async(str(size_file))
                    if size_content:
                        size_bytes = int(size_content.strip()) * 512  # sectors to bytes

                # Get model
                model_file = device_dir / 'device/model'
                model = None
                if model_file.exists():
                    model = (await self.read_file_async(str(model_file)) or '').strip()

                # Determine type
                rotational_file = device_dir / 'queue/rotational'
                device_type = 'Unknown'
                if rotational_file.exists():
                    rotational = (await self.read_file_async(str(rotational_file)) or '').strip()
                    device_type = 'HDD' if rotational == '1' else 'SSD'

                # Check if NVMe
                if name.startswith('nvme'):
                    device_type = 'NVMe'

                # Get removable status
                removable_file = device_dir / 'removable'
                is_removable = False
                if removable_file.exists():
                    is_removable = (await self.read_file_async(str(removable_file)) or '').strip() == '1'

                # Get partitions
                partitions = []
                for item in device_dir.iterdir():
                    if item.name.startswith(name) and item.name != name:
                        part_size_file = item / 'size'
                        if part_size_file.exists():
                            part_size = int((await self.read_file_async(str(part_size_file)) or '0').strip()) * 512
                            partitions.append({
                                'name': item.name,
                                'size_bytes': part_size,
                            })

                # Get mount points
                mount_points = await self._get_mount_points(name)

                # Determine access level
                access_level = await self._check_device_access(device_path)

                # Check if system disk
                is_system = any(mp in ('/', '/boot') for mp in mount_points)

                devices.append(StorageDevice(
                    device_path=device_path,
                    name=name,
                    model=model,
                    serial=None,
                    size_bytes=size_bytes,
                    type=device_type,
                    is_removable=is_removable,
                    partitions=partitions,
                    mount_points=mount_points,
                    filesystem=None,
                    access_level=access_level,
                    is_system_disk=is_system,
                    smart_status=None,
                ))
        except Exception as e:
            self.add_warning(f"Failed to get storage devices: {e}")

        return devices

    async def _get_mount_points(self, device_name: str) -> list[str]:
        """Get mount points for a device."""
        mount_points = []

        mounts = await self.read_file_async('/proc/mounts')
        if mounts:
            for line in mounts.split('\n'):
                parts = line.split()
                if len(parts) >= 2:
                    if device_name in parts[0]:
                        mount_points.append(parts[1])

        return mount_points

    async def _check_device_access(self, device_path: str) -> DeviceAccessLevel:
        """Check access level for a device."""
        if not Path(device_path).exists():
            return DeviceAccessLevel.NONE

        readable = os.access(device_path, os.R_OK)
        writable = os.access(device_path, os.W_OK)

        if readable and writable:
            return DeviceAccessLevel.READ_WRITE
        elif readable:
            return DeviceAccessLevel.READ_ONLY
        else:
            return DeviceAccessLevel.NONE

    async def _get_network_interfaces(self) -> list[NetworkInterface]:
        """Get network interface information."""
        interfaces = []

        try:
            net_path = Path('/sys/class/net')
            if not net_path.exists():
                return interfaces

            for iface_dir in net_path.iterdir():
                name = iface_dir.name

                # Get MAC address
                mac_file = iface_dir / 'address'
                mac = None
                if mac_file.exists():
                    mac = (await self.read_file_async(str(mac_file)) or '').strip()
                    if mac == '00:00:00:00:00:00':
                        mac = None

                # Get operational state
                operstate_file = iface_dir / 'operstate'
                is_up = False
                if operstate_file.exists():
                    state = (await self.read_file_async(str(operstate_file)) or '').strip()
                    is_up = state == 'up'

                # Check if loopback
                is_loopback = name == 'lo'

                # Check if virtual
                device_link = iface_dir / 'device'
                is_virtual = not device_link.exists()

                # Get MTU
                mtu_file = iface_dir / 'mtu'
                mtu = 1500
                if mtu_file.exists():
                    mtu_content = (await self.read_file_async(str(mtu_file)) or '').strip()
                    if mtu_content:
                        mtu = int(mtu_content)

                # Get speed
                speed_file = iface_dir / 'speed'
                speed = None
                if speed_file.exists():
                    try:
                        # Use silent_if_missing=True since reading speed can fail with EINVAL
                        # for virtual interfaces (bridges, VPN, loopback, etc.)
                        speed_content = (await self.read_file_async(str(speed_file), silent_if_missing=True) or '').strip()
                        if speed_content and speed_content != '-1':
                            speed = int(speed_content)
                    except (ValueError, OSError):
                        # Speed file exists but reading failed (common for virtual interfaces)
                        pass

                # Get IP addresses using ip command
                ipv4_addrs, ipv6_addrs = await self._get_ip_addresses(name)

                interfaces.append(NetworkInterface(
                    name=name,
                    mac_address=mac,
                    ipv4_addresses=ipv4_addrs,
                    ipv6_addresses=ipv6_addrs,
                    is_up=is_up,
                    is_loopback=is_loopback,
                    is_virtual=is_virtual,
                    speed_mbps=speed,
                    mtu=mtu,
                    driver=None,
                    access_level=DeviceAccessLevel.SHARED,
                ))
        except Exception as e:
            self.add_warning(f"Failed to get network interfaces: {e}")

        return interfaces

    async def _get_ip_addresses(self, iface: str) -> tuple[list[str], list[str]]:
        """Get IP addresses for an interface."""
        ipv4_addrs = []
        ipv6_addrs = []

        ret, stdout, _ = await self.run_command(['ip', 'addr', 'show', iface], timeout=5)
        if ret == 0 and stdout:
            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith('inet '):
                    parts = line.split()
                    if len(parts) >= 2:
                        ipv4_addrs.append(parts[1].split('/')[0])
                elif line.startswith('inet6 '):
                    parts = line.split()
                    if len(parts) >= 2:
                        ipv6_addrs.append(parts[1].split('/')[0])

        return ipv4_addrs, ipv6_addrs

    async def _get_gpu_info(self) -> list[GPUInfo]:
        """Get GPU information."""
        gpus = []

        try:
            # Check for NVIDIA GPUs
            ret, stdout, _ = await self.run_command(
                ['nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used,pci.bus_id',
                 '--format=csv,noheader,nounits'],
                timeout=10,
            )

            if ret == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 5:
                        gpus.append(GPUInfo(
                            name=parts[0],
                            vendor='NVIDIA',
                            driver='nvidia',
                            driver_version=parts[1],
                            memory_total_bytes=int(float(parts[2])) * 1024 * 1024 if parts[2] else None,
                            memory_used_bytes=int(float(parts[3])) * 1024 * 1024 if parts[3] else None,
                            pci_bus_id=parts[4],
                            is_integrated=False,
                            compute_capability=None,
                            access_level=DeviceAccessLevel.SHARED,
                        ))

            # Check for AMD GPUs via sysfs
            drm_path = Path('/sys/class/drm')
            if drm_path.exists():
                for card_dir in drm_path.iterdir():
                    if card_dir.name.startswith('card') and '-' not in card_dir.name:
                        device_path = card_dir / 'device'
                        if device_path.exists():
                            vendor_file = device_path / 'vendor'
                            if vendor_file.exists():
                                vendor_id = (await self.read_file_async(str(vendor_file)) or '').strip()
                                if vendor_id == '0x1002':  # AMD
                                    name_file = device_path / 'product_name'
                                    name = 'AMD GPU'
                                    if name_file.exists():
                                        name = (await self.read_file_async(str(name_file)) or name).strip()

                                    gpus.append(GPUInfo(
                                        name=name,
                                        vendor='AMD',
                                        driver='amdgpu',
                                        driver_version=None,
                                        memory_total_bytes=None,
                                        memory_used_bytes=None,
                                        pci_bus_id=None,
                                        is_integrated=False,
                                        compute_capability=None,
                                        access_level=DeviceAccessLevel.SHARED,
                                    ))

            # Check for Intel integrated GPU
            ret, stdout, _ = await self.run_command(['lspci'], timeout=5)
            if ret == 0 and stdout:
                for line in stdout.split('\n'):
                    if 'VGA' in line and 'Intel' in line:
                        gpus.append(GPUInfo(
                            name=line.split(':')[-1].strip() if ':' in line else 'Intel Integrated',
                            vendor='Intel',
                            driver='i915',
                            driver_version=None,
                            memory_total_bytes=None,
                            memory_used_bytes=None,
                            pci_bus_id=line.split()[0] if line.split() else None,
                            is_integrated=True,
                            compute_capability=None,
                            access_level=DeviceAccessLevel.SHARED,
                        ))
        except Exception as e:
            self.add_warning(f"Failed to get GPU info: {e}")

        return gpus

    async def _get_usb_devices(self) -> list[USBDevice]:
        """Get USB device information."""
        devices = []

        try:
            ret, stdout, _ = await self.run_command(['lsusb'], timeout=10)
            if ret == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    # Parse: Bus 001 Device 002: ID 8087:0026 Intel Corp. ...
                    match = re.match(
                        r'Bus (\d+) Device (\d+): ID ([0-9a-f]{4}):([0-9a-f]{4})\s*(.*)',
                        line,
                        re.IGNORECASE,
                    )
                    if match:
                        bus, device_num, vendor_id, product_id, description = match.groups()
                        devices.append(USBDevice(
                            bus=int(bus),
                            device=int(device_num),
                            vendor_id=vendor_id,
                            product_id=product_id,
                            vendor_name=None,
                            product_name=description.strip() if description else None,
                            device_class='Unknown',
                            serial=None,
                            access_level=DeviceAccessLevel.SHARED,
                        ))
        except Exception as e:
            self.add_warning(f"Failed to get USB devices: {e}")

        return devices

    async def _check_virtualization(self) -> tuple[bool, str | None, str | None]:
        """Check if running in a virtual machine."""
        is_vm = False
        hypervisor = None
        vm_type = None

        # Check /proc/cpuinfo for hypervisor flag
        cpuinfo = await self.read_file_async('/proc/cpuinfo')
        if cpuinfo and 'hypervisor' in cpuinfo:
            is_vm = True

        # Check systemd-detect-virt
        ret, stdout, _ = await self.run_command(['systemd-detect-virt'], timeout=5)
        if ret == 0 and stdout.strip() != 'none':
            is_vm = True
            vm_type = stdout.strip()
            hypervisor = vm_type

        # Check DMI for VM vendors
        if not is_vm:
            product = await self.read_file_async('/sys/class/dmi/id/product_name')
            if product:
                product = product.lower()
                vm_markers = {
                    'vmware': 'VMware',
                    'virtualbox': 'VirtualBox',
                    'kvm': 'KVM',
                    'qemu': 'QEMU',
                    'hyper-v': 'Hyper-V',
                    'xen': 'Xen',
                }
                for marker, name in vm_markers.items():
                    if marker in product:
                        is_vm = True
                        hypervisor = name
                        vm_type = name.lower()
                        break

        return is_vm, hypervisor, vm_type

    async def _build_access_summary(
        self,
        storage: list[StorageDevice],
        network: list[NetworkInterface],
        gpus: list[GPUInfo],
        usb: list[USBDevice],
    ) -> dict[str, DeviceAccessLevel]:
        """Build device access summary."""
        summary = {}

        for device in storage:
            summary[f'storage:{device.name}'] = device.access_level

        for iface in network:
            summary[f'network:{iface.name}'] = iface.access_level

        for i, gpu in enumerate(gpus):
            summary[f'gpu:{i}:{gpu.name}'] = gpu.access_level

        for device in usb:
            summary[f'usb:{device.bus}:{device.device}'] = device.access_level

        return summary
