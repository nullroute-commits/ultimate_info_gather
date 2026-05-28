"""
Proxmox VE collector.

Collects Proxmox cluster details, node information, virtual machines,
containers, storage pools, and network configuration using both the
Proxmox API (via pvesh CLI) and local system inspection.

Reference documentation:
- Proxmox VE API: https://pve.proxmox.com/pve-docs/api-viewer/
- Proxmox VE Admin Guide: https://pve.proxmox.com/pve-docs/pve-admin-guide.html
- pvesh CLI: https://pve.proxmox.com/pve-docs/pvesh.1.html
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models.environment import EnvironmentState
from ..models.permissions import PermissionsInfo
from ..models.proxmox import (
    ProxmoxClusterInfo,
    ProxmoxContainer,
    ProxmoxInfo,
    ProxmoxNetworkInterface,
    ProxmoxNodeInfo,
    ProxmoxNodeStatus,
    ProxmoxStorage,
    ProxmoxVersion,
    ProxmoxVM,
    StorageContentType,
    StorageType,
    VMStatus,
)
from .base import BaseCollector


class ProxmoxCollector(BaseCollector["ProxmoxInfo"]):
    """
    Collects comprehensive Proxmox VE information.

    Uses `pvesh` (Proxmox VE Shell) CLI to query the local API and
    system files to gather:
    - Proxmox VE version and cluster status
    - Node details (CPU, memory, uptime, kernel)
    - Virtual machines (QEMU) list and status
    - LXC containers list and status
    - Storage pools configuration and usage
    - Network interfaces managed by Proxmox
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
        self._environment_state = environment_state
        self._permissions_info = permissions_info

    async def collect(self) -> ProxmoxInfo:
        """Collect Proxmox VE information."""
        timestamp = datetime.now()

        # First check if this is a Proxmox host
        is_proxmox = await self._is_proxmox_host()

        if not is_proxmox:
            return ProxmoxInfo(
                timestamp=timestamp,
                is_proxmox_host=False,
                version=None,
                cluster=None,
                nodes=[],
                virtual_machines=[],
                containers=[],
                storage_pools=[],
                network_interfaces=[],
            )

        # Gather all Proxmox data in parallel where possible
        results = await self.gather_with_errors(
            self._collect_version(),
            self._collect_cluster_info(),
            self._collect_nodes(),
            self._collect_vms(),
            self._collect_containers(),
            self._collect_storage(),
            self._collect_network(),
        )

        version = results[0] if results[0] else None
        cluster = results[1] if results[1] else None
        nodes = results[2] if results[2] else []
        vms = results[3] if results[3] else []
        containers = results[4] if results[4] else []
        storage_pools = results[5] if results[5] else []
        network_interfaces = results[6] if results[6] else []

        # Calculate summary stats
        total_vms = len(vms)
        running_vms = sum(1 for vm in vms if vm.status == VMStatus.RUNNING)
        total_containers = len(containers)
        running_containers = sum(1 for ct in containers if ct.status == VMStatus.RUNNING)
        total_storage = sum(s.total_bytes or 0 for s in storage_pools)
        used_storage = sum(s.used_bytes or 0 for s in storage_pools)

        return ProxmoxInfo(
            timestamp=timestamp,
            is_proxmox_host=True,
            version=version,
            cluster=cluster,
            nodes=nodes,
            virtual_machines=vms,
            containers=containers,
            storage_pools=storage_pools,
            network_interfaces=network_interfaces,
            total_vms=total_vms,
            running_vms=running_vms,
            total_containers=total_containers,
            running_containers=running_containers,
            total_storage_bytes=total_storage,
            used_storage_bytes=used_storage,
        )

    async def _is_proxmox_host(self) -> bool:
        """
        Detect if the current system is a Proxmox VE host.

        Checks for:
        - /etc/pve directory (Proxmox cluster filesystem)
        - pveversion command availability
        - /usr/bin/pvesh binary
        """
        # Check for /etc/pve (pmxcfs - Proxmox cluster file system)
        pve_dir = Path("/etc/pve")
        if pve_dir.is_dir():
            return True

        # Check for pvesh binary
        pvesh_path = Path("/usr/bin/pvesh")
        if pvesh_path.exists():
            return True

        # Try running pveversion
        returncode, stdout, _ = await self.run_command(
            ["pveversion"], timeout=5.0
        )
        return bool(returncode == 0 and stdout.strip())

    async def _pvesh_get(self, path: str, timeout: float = 30.0) -> dict | list | None:
        """
        Execute pvesh get command and parse JSON output.

        pvesh is the Proxmox VE API shell that provides CLI access to the
        REST API without needing authentication tokens.

        Args:
            path: API path (e.g., /cluster/status, /nodes)
            timeout: Command timeout in seconds

        Returns:
            Parsed JSON response or None on failure
        """
        returncode, stdout, stderr = await self.run_command(
            ["pvesh", "get", path, "--output-format", "json"],
            timeout=timeout,
        )

        if returncode != 0:
            if stderr.strip():
                self.add_warning(f"pvesh get {path} failed: {stderr.strip()}")
            return None

        if not stdout.strip():
            return None

        try:
            result: dict | list = json.loads(stdout)
            return result
        except json.JSONDecodeError as e:
            self.add_warning(f"Failed to parse pvesh output for {path}: {e}")
            return None

    async def _collect_version(self) -> ProxmoxVersion | None:
        """Collect Proxmox VE version information."""
        # Try pvesh first
        data = await self._pvesh_get("/version")
        if isinstance(data, dict):
            return ProxmoxVersion(
                version=data.get("version", "unknown"),
                release=data.get("release", "unknown"),
                repo_id=data.get("repoid"),
                kernel_version=data.get("kernel"),
            )

        # Fallback: parse pveversion output
        returncode, stdout, _ = await self.run_command(
            ["pveversion", "--verbose"], timeout=10.0
        )
        if returncode == 0 and stdout.strip():
            version = "unknown"
            release = "unknown"
            kernel = None

            for line in stdout.strip().splitlines():
                if line.startswith("pve-manager/"):
                    # Format: pve-manager/8.1.3/b46aac3b42da5d15
                    parts = line.split("/")
                    if len(parts) >= 2:
                        version = parts[1]
                    if len(parts) >= 3:
                        release = parts[2]
                elif line.startswith("proxmox-kernel"):
                    kernel = line.split("/")[1] if "/" in line else line

            return ProxmoxVersion(
                version=version,
                release=release,
                repo_id=None,
                kernel_version=kernel,
            )

        return None

    async def _collect_cluster_info(self) -> ProxmoxClusterInfo | None:
        """Collect Proxmox cluster information."""
        data = await self._pvesh_get("/cluster/status")
        if not isinstance(data, list):
            return None

        cluster_name = None
        cluster_version = None
        quorate = None
        cluster_id = None
        nodes_count = 0

        for item in data:
            item_type = item.get("type", "")
            if item_type == "cluster":
                cluster_name = item.get("name")
                cluster_version = item.get("version")
                quorate = bool(item.get("quorate"))
                cluster_id = item.get("id")
            elif item_type == "node":
                nodes_count += 1

        return ProxmoxClusterInfo(
            name=cluster_name,
            version=cluster_version,
            nodes_count=max(nodes_count, 1),
            quorate=quorate,
            cluster_id=cluster_id,
        )

    async def _collect_nodes(self) -> list[ProxmoxNodeInfo]:
        """Collect information about all Proxmox nodes."""
        data = await self._pvesh_get("/nodes")
        if not isinstance(data, list):
            return []

        nodes = []
        for node_data in data:
            status_str = node_data.get("status", "unknown")
            status = self._parse_node_status(status_str)

            # CPU usage is returned as a fraction (0.0 - 1.0)
            cpu_usage = node_data.get("cpu")
            cpu_percent = (cpu_usage * 100) if cpu_usage is not None else None

            mem_total = node_data.get("maxmem")
            mem_used = node_data.get("mem")
            mem_free = (mem_total - mem_used) if mem_total and mem_used else None

            disk_total = node_data.get("maxdisk")
            disk_used = node_data.get("disk")

            node = ProxmoxNodeInfo(
                name=node_data.get("node", "unknown"),
                status=status,
                cpu_count=node_data.get("maxcpu"),
                cpu_usage_percent=cpu_percent,
                memory_total_bytes=mem_total,
                memory_used_bytes=mem_used,
                memory_free_bytes=mem_free,
                swap_total_bytes=None,
                swap_used_bytes=None,
                uptime_seconds=node_data.get("uptime"),
                kernel_version=None,
                pve_version=None,
                cpu_model=None,
                local_disk_total_bytes=disk_total,
                local_disk_used_bytes=disk_used,
            )
            nodes.append(node)

        # Try to get detailed info for each node
        for node in nodes:
            await self._enrich_node_details(node)

        return nodes

    async def _enrich_node_details(self, node: ProxmoxNodeInfo) -> None:
        """Enrich node with detailed status information."""
        data = await self._pvesh_get(f"/nodes/{node.name}/status")
        if not isinstance(data, dict):
            return

        # CPU model
        cpu_info = data.get("cpuinfo", {})
        if isinstance(cpu_info, dict):
            node.cpu_model = cpu_info.get("model")
            if not node.cpu_count:
                cpus = cpu_info.get("cpus")
                if cpus:
                    node.cpu_count = int(cpus)

        # Swap info
        swap_info = data.get("swap", {})
        if isinstance(swap_info, dict):
            node.swap_total_bytes = swap_info.get("total")
            node.swap_used_bytes = swap_info.get("used")

        # Kernel version
        kversion = data.get("kversion")
        if kversion:
            node.kernel_version = kversion

        # PVE version
        pve_ver = data.get("pveversion")
        if pve_ver:
            node.pve_version = pve_ver

    async def _collect_vms(self) -> list[ProxmoxVM]:
        """Collect virtual machine information from all nodes."""
        # Get cluster-wide resource list for VMs
        data = await self._pvesh_get("/cluster/resources?type=vm")
        if not isinstance(data, list):
            return []

        vms = []
        for vm_data in data:
            # Filter for QEMU VMs only (not LXC)
            if vm_data.get("type") != "qemu":
                continue

            status = self._parse_vm_status(vm_data.get("status", "unknown"))
            cpu_usage = vm_data.get("cpu")
            cpu_percent = (cpu_usage * 100) if cpu_usage is not None else None

            tags_str = vm_data.get("tags", "")
            tags = [t.strip() for t in tags_str.split(";") if t.strip()] if tags_str else []

            vm = ProxmoxVM(
                vmid=vm_data.get("vmid", 0),
                name=vm_data.get("name", f"vm-{vm_data.get('vmid', 'unknown')}"),
                status=status,
                node=vm_data.get("node", "unknown"),
                cpu_cores=vm_data.get("maxcpu"),
                cpu_usage_percent=cpu_percent,
                memory_max_bytes=vm_data.get("maxmem"),
                memory_used_bytes=vm_data.get("mem"),
                disk_total_bytes=vm_data.get("maxdisk"),
                disk_used_bytes=vm_data.get("disk"),
                uptime_seconds=vm_data.get("uptime"),
                template=bool(vm_data.get("template", 0)),
                tags=tags,
                ha_state=vm_data.get("hastate"),
                agent_running=None,
            )
            vms.append(vm)

        return vms

    async def _collect_containers(self) -> list[ProxmoxContainer]:
        """Collect LXC container information from all nodes."""
        data = await self._pvesh_get("/cluster/resources?type=vm")
        if not isinstance(data, list):
            return []

        containers = []
        for ct_data in data:
            # Filter for LXC containers only
            if ct_data.get("type") != "lxc":
                continue

            status = self._parse_vm_status(ct_data.get("status", "unknown"))
            cpu_usage = ct_data.get("cpu")
            cpu_percent = (cpu_usage * 100) if cpu_usage is not None else None

            tags_str = ct_data.get("tags", "")
            tags = [t.strip() for t in tags_str.split(";") if t.strip()] if tags_str else []

            container = ProxmoxContainer(
                vmid=ct_data.get("vmid", 0),
                name=ct_data.get("name", f"ct-{ct_data.get('vmid', 'unknown')}"),
                status=status,
                node=ct_data.get("node", "unknown"),
                cpu_cores=ct_data.get("maxcpu"),
                cpu_usage_percent=cpu_percent,
                memory_max_bytes=ct_data.get("maxmem"),
                memory_used_bytes=ct_data.get("mem"),
                disk_total_bytes=ct_data.get("maxdisk"),
                disk_used_bytes=ct_data.get("disk"),
                swap_total_bytes=ct_data.get("maxswap"),
                swap_used_bytes=ct_data.get("swap"),
                uptime_seconds=ct_data.get("uptime"),
                template=bool(ct_data.get("template", 0)),
                tags=tags,
                ha_state=ct_data.get("hastate"),
            )
            containers.append(container)

        return containers

    async def _collect_storage(self) -> list[ProxmoxStorage]:
        """Collect storage pool information."""
        data = await self._pvesh_get("/storage")
        if not isinstance(data, list):
            return []

        storage_pools = []
        for storage_data in data:
            storage_type = self._parse_storage_type(storage_data.get("type", ""))
            content_str = storage_data.get("content", "")
            content_types = self._parse_content_types(content_str)

            pool = ProxmoxStorage(
                storage_id=storage_data.get("storage", "unknown"),
                node=storage_data.get("node"),
                storage_type=storage_type,
                content_types=content_types,
                total_bytes=storage_data.get("total"),
                used_bytes=storage_data.get("used"),
                available_bytes=storage_data.get("avail"),
                enabled=bool(storage_data.get("enabled", 1)),
                shared=bool(storage_data.get("shared", 0)),
                path=storage_data.get("path"),
            )
            storage_pools.append(pool)

        # Try to get usage data from cluster resources
        usage_data = await self._pvesh_get("/cluster/resources?type=storage")
        if isinstance(usage_data, list):
            usage_map = {}
            for item in usage_data:
                sid = item.get("storage")
                if sid:
                    usage_map[sid] = item

            for pool in storage_pools:
                usage = usage_map.get(pool.storage_id)
                if usage:
                    if not pool.total_bytes:
                        pool.total_bytes = usage.get("maxdisk")
                    if not pool.used_bytes:
                        pool.used_bytes = usage.get("disk")

        return storage_pools

    async def _collect_network(self) -> list[ProxmoxNetworkInterface]:
        """Collect Proxmox-managed network interfaces for the local node."""
        # Get local node name
        node_name = await self._get_local_node_name()
        if not node_name:
            return []

        data = await self._pvesh_get(f"/nodes/{node_name}/network")
        if not isinstance(data, list):
            return []

        interfaces = []
        for iface_data in data:
            iface = ProxmoxNetworkInterface(
                iface=iface_data.get("iface", "unknown"),
                interface_type=iface_data.get("type", "unknown"),
                address=iface_data.get("address"),
                netmask=iface_data.get("netmask"),
                gateway=iface_data.get("gateway"),
                bridge_ports=iface_data.get("bridge_ports"),
                bond_slaves=iface_data.get("slaves"),
                vlan_id=iface_data.get("vlan-id"),
                active=bool(iface_data.get("active", 0)),
                autostart=bool(iface_data.get("autostart", 0)),
                comments=iface_data.get("comments"),
            )
            interfaces.append(iface)

        return interfaces

    async def _get_local_node_name(self) -> str | None:
        """Get the local Proxmox node name."""
        # Try reading from /etc/hostname (standard on Proxmox)
        content = await self.read_file_async("/etc/hostname", silent_if_missing=True)
        if content:
            return content.strip()

        # Fallback: use hostname command
        returncode, stdout, _ = await self.run_command(["hostname"], timeout=5.0)
        if returncode == 0 and stdout.strip():
            return stdout.strip()

        return None

    @staticmethod
    def _parse_node_status(status_str: str) -> ProxmoxNodeStatus:
        """Parse node status string."""
        status_map = {
            "online": ProxmoxNodeStatus.ONLINE,
            "offline": ProxmoxNodeStatus.OFFLINE,
        }
        return status_map.get(status_str.lower(), ProxmoxNodeStatus.UNKNOWN)

    @staticmethod
    def _parse_vm_status(status_str: str) -> VMStatus:
        """Parse VM/container status string."""
        status_map = {
            "running": VMStatus.RUNNING,
            "stopped": VMStatus.STOPPED,
            "paused": VMStatus.PAUSED,
            "suspended": VMStatus.SUSPENDED,
        }
        return status_map.get(status_str.lower(), VMStatus.UNKNOWN)

    @staticmethod
    def _parse_storage_type(type_str: str) -> StorageType:
        """Parse storage type string."""
        type_map = {
            "dir": StorageType.DIR,
            "lvm": StorageType.LVM,
            "lvmthin": StorageType.LVMTHIN,
            "zfs": StorageType.ZFS,
            "zfspool": StorageType.ZFSPOOL,
            "nfs": StorageType.NFS,
            "cifs": StorageType.CIFS,
            "iscsi": StorageType.ISCSI,
            "rbd": StorageType.CEPH,
            "cephfs": StorageType.CEPH,
            "pbs": StorageType.PBS,
        }
        return type_map.get(type_str.lower(), StorageType.OTHER)

    @staticmethod
    def _parse_content_types(content_str: str) -> list[StorageContentType]:
        """Parse storage content types from comma-separated string."""
        content_map = {
            "images": StorageContentType.IMAGES,
            "rootdir": StorageContentType.ROOTDIR,
            "vztmpl": StorageContentType.VZTMPL,
            "backup": StorageContentType.BACKUP,
            "iso": StorageContentType.ISO,
            "snippets": StorageContentType.SNIPPETS,
        }
        types = []
        for item in content_str.split(","):
            ct = content_map.get(item.strip().lower())
            if ct:
                types.append(ct)
        return types
