"""
Tests for Proxmox VE collector.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.collectors.proxmox_collector import ProxmoxCollector
from src.models.proxmox import (
    ProxmoxClusterInfo,
    ProxmoxInfo,
    ProxmoxNodeInfo,
    ProxmoxNodeStatus,
    ProxmoxVersion,
    StorageContentType,
    StorageType,
    VMStatus,
)


@pytest.mark.asyncio
async def test_proxmox_collector_non_proxmox_host():
    """Test collector on a non-Proxmox host returns is_proxmox_host=False."""
    collector = ProxmoxCollector()
    result = await collector.safe_collect()

    assert result.success is True
    assert result.data is not None
    assert result.data.is_proxmox_host is False
    assert result.data.nodes == []
    assert result.data.virtual_machines == []
    assert result.data.containers == []


@pytest.mark.asyncio
async def test_proxmox_collector_detects_proxmox_host():
    """Test collector detects Proxmox host via /etc/pve directory."""
    collector = ProxmoxCollector()

    with patch("pathlib.Path.is_dir", return_value=True):
        is_proxmox = await collector._is_proxmox_host()
        assert is_proxmox is True


@pytest.mark.asyncio
async def test_proxmox_collector_version_parsing():
    """Test version parsing from pvesh output."""
    collector = ProxmoxCollector()

    mock_response = {
        "version": "8.1.3",
        "release": "1",
        "repoid": "b46aac3b42da5d15",
        "kernel": "6.5.13-3-pve",
    }

    with patch.object(collector, "_pvesh_get", return_value=mock_response):
        version = await collector._collect_version()

    assert version is not None
    assert version.version == "8.1.3"
    assert version.release == "1"
    assert version.repo_id == "b46aac3b42da5d15"
    assert version.kernel_version == "6.5.13-3-pve"


@pytest.mark.asyncio
async def test_proxmox_collector_cluster_info():
    """Test cluster info parsing."""
    collector = ProxmoxCollector()

    mock_response = [
        {
            "type": "cluster",
            "name": "my-cluster",
            "version": 3,
            "quorate": 1,
            "id": "cluster-id-123",
        },
        {"type": "node", "name": "pve1", "online": 1},
        {"type": "node", "name": "pve2", "online": 1},
    ]

    with patch.object(collector, "_pvesh_get", return_value=mock_response):
        cluster = await collector._collect_cluster_info()

    assert cluster is not None
    assert cluster.name == "my-cluster"
    assert cluster.version == 3
    assert cluster.nodes_count == 2
    assert cluster.quorate is True


@pytest.mark.asyncio
async def test_proxmox_collector_nodes():
    """Test node info parsing."""
    collector = ProxmoxCollector()

    mock_nodes = [
        {
            "node": "pve1",
            "status": "online",
            "cpu": 0.25,
            "maxcpu": 8,
            "maxmem": 34359738368,
            "mem": 17179869184,
            "uptime": 86400,
            "maxdisk": 500107862016,
            "disk": 200000000000,
        },
    ]

    mock_status = {
        "cpuinfo": {"model": "Intel Xeon E5-2680", "cpus": 8},
        "swap": {"total": 8589934592, "used": 1073741824},
        "kversion": "Linux 6.5.13-3-pve",
        "pveversion": "pve-manager/8.1.3/b46aac3b42da5d15",
    }

    async def mock_pvesh_get(path: str) -> dict | list | None:
        if path == "/nodes":
            return mock_nodes
        if path == "/nodes/pve1/status":
            return mock_status
        return None

    with patch.object(collector, "_pvesh_get", side_effect=mock_pvesh_get):
        nodes = await collector._collect_nodes()

    assert len(nodes) == 1
    node = nodes[0]
    assert node.name == "pve1"
    assert node.status == ProxmoxNodeStatus.ONLINE
    assert node.cpu_usage_percent == 25.0
    assert node.cpu_count == 8
    assert node.memory_total_bytes == 34359738368
    assert node.memory_used_bytes == 17179869184
    assert node.kernel_version == "Linux 6.5.13-3-pve"
    assert node.cpu_model == "Intel Xeon E5-2680"


@pytest.mark.asyncio
async def test_proxmox_collector_vms():
    """Test VM list parsing."""
    collector = ProxmoxCollector()

    mock_response = [
        {
            "type": "qemu",
            "vmid": 100,
            "name": "test-vm",
            "status": "running",
            "node": "pve1",
            "maxcpu": 4,
            "cpu": 0.1,
            "maxmem": 8589934592,
            "mem": 4294967296,
            "maxdisk": 107374182400,
            "disk": 50000000000,
            "uptime": 3600,
            "template": 0,
            "tags": "production;web",
        },
        {
            "type": "lxc",
            "vmid": 200,
            "name": "test-ct",
            "status": "running",
            "node": "pve1",
        },
    ]

    with patch.object(collector, "_pvesh_get", return_value=mock_response):
        vms = await collector._collect_vms()

    # Should only include QEMU VMs, not LXC
    assert len(vms) == 1
    vm = vms[0]
    assert vm.vmid == 100
    assert vm.name == "test-vm"
    assert vm.status == VMStatus.RUNNING
    assert vm.cpu_cores == 4
    assert vm.cpu_usage_percent == 10.0
    assert vm.tags == ["production", "web"]


@pytest.mark.asyncio
async def test_proxmox_collector_containers():
    """Test container list parsing."""
    collector = ProxmoxCollector()

    mock_response = [
        {
            "type": "qemu",
            "vmid": 100,
            "name": "test-vm",
            "status": "running",
            "node": "pve1",
        },
        {
            "type": "lxc",
            "vmid": 200,
            "name": "test-ct",
            "status": "stopped",
            "node": "pve1",
            "maxcpu": 2,
            "cpu": 0,
            "maxmem": 2147483648,
            "mem": 0,
            "maxdisk": 21474836480,
            "disk": 5000000000,
            "template": 0,
            "tags": "",
        },
    ]

    with patch.object(collector, "_pvesh_get", return_value=mock_response):
        containers = await collector._collect_containers()

    # Should only include LXC containers, not QEMU VMs
    assert len(containers) == 1
    ct = containers[0]
    assert ct.vmid == 200
    assert ct.name == "test-ct"
    assert ct.status == VMStatus.STOPPED


@pytest.mark.asyncio
async def test_proxmox_collector_storage():
    """Test storage pool parsing."""
    collector = ProxmoxCollector()

    mock_storage = [
        {
            "storage": "local",
            "type": "dir",
            "content": "iso,vztmpl,backup",
            "enabled": 1,
            "shared": 0,
            "path": "/var/lib/vz",
        },
        {
            "storage": "local-lvm",
            "type": "lvmthin",
            "content": "images,rootdir",
            "enabled": 1,
            "shared": 0,
        },
    ]

    mock_usage = [
        {
            "storage": "local",
            "maxdisk": 107374182400,
            "disk": 50000000000,
        },
        {
            "storage": "local-lvm",
            "maxdisk": 500107862016,
            "disk": 200000000000,
        },
    ]

    async def mock_pvesh_get(path: str) -> dict | list | None:
        if path == "/storage":
            return mock_storage
        if path == "/cluster/resources?type=storage":
            return mock_usage
        return None

    with patch.object(collector, "_pvesh_get", side_effect=mock_pvesh_get):
        pools = await collector._collect_storage()

    assert len(pools) == 2
    assert pools[0].storage_id == "local"
    assert pools[0].storage_type == StorageType.DIR
    assert StorageContentType.ISO in pools[0].content_types
    assert StorageContentType.BACKUP in pools[0].content_types
    assert pools[0].total_bytes == 107374182400

    assert pools[1].storage_id == "local-lvm"
    assert pools[1].storage_type == StorageType.LVMTHIN
    assert StorageContentType.IMAGES in pools[1].content_types


@pytest.mark.asyncio
async def test_proxmox_collector_network():
    """Test network interface parsing."""
    collector = ProxmoxCollector()

    mock_network = [
        {
            "iface": "vmbr0",
            "type": "bridge",
            "address": "192.168.1.10",
            "netmask": "255.255.255.0",
            "gateway": "192.168.1.1",
            "bridge_ports": "eno1",
            "active": 1,
            "autostart": 1,
        },
        {
            "iface": "eno1",
            "type": "eth",
            "active": 1,
            "autostart": 1,
        },
    ]

    async def mock_pvesh_get(path: str) -> dict | list | None:
        if "/network" in path:
            return mock_network
        return None

    with (
        patch.object(collector, "_pvesh_get", side_effect=mock_pvesh_get),
        patch.object(collector, "_get_local_node_name", return_value="pve1"),
    ):
        interfaces = await collector._collect_network()

    assert len(interfaces) == 2
    assert interfaces[0].iface == "vmbr0"
    assert interfaces[0].interface_type == "bridge"
    assert interfaces[0].address == "192.168.1.10"
    assert interfaces[0].bridge_ports == "eno1"


@pytest.mark.asyncio
async def test_proxmox_info_to_dict():
    """Test ProxmoxInfo serialization."""
    info = ProxmoxInfo(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        is_proxmox_host=True,
        version=ProxmoxVersion(
            version="8.1.3",
            release="1",
            repo_id="abc123",
            kernel_version="6.5.13-3-pve",
        ),
        cluster=ProxmoxClusterInfo(
            name="test-cluster",
            version=3,
            nodes_count=2,
            quorate=True,
            cluster_id="cluster-1",
        ),
        nodes=[],
        virtual_machines=[],
        containers=[],
        storage_pools=[],
        network_interfaces=[],
        total_vms=5,
        running_vms=3,
        total_containers=10,
        running_containers=8,
    )

    data = info.to_dict()
    assert data["is_proxmox_host"] is True
    assert data["version"]["version"] == "8.1.3"
    assert data["cluster"]["name"] == "test-cluster"
    assert data["total_vms"] == 5
    assert data["running_vms"] == 3


@pytest.mark.asyncio
async def test_proxmox_info_summary():
    """Test ProxmoxInfo summary generation."""
    info = ProxmoxInfo(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        is_proxmox_host=True,
        version=ProxmoxVersion(
            version="8.1.3", release="1", repo_id=None, kernel_version=None
        ),
        cluster=ProxmoxClusterInfo(
            name="prod-cluster", version=3, nodes_count=3, quorate=True, cluster_id=None
        ),
        nodes=[
            ProxmoxNodeInfo(
                name="pve1",
                status=ProxmoxNodeStatus.ONLINE,
                cpu_count=8,
                cpu_usage_percent=25.0,
                memory_total_bytes=34359738368,
                memory_used_bytes=17179869184,
                memory_free_bytes=17179869184,
                swap_total_bytes=None,
                swap_used_bytes=None,
                uptime_seconds=86400,
                kernel_version=None,
                pve_version=None,
                cpu_model=None,
                local_disk_total_bytes=None,
                local_disk_used_bytes=None,
            ),
        ],
        virtual_machines=[],
        containers=[],
        storage_pools=[],
        network_interfaces=[],
        total_vms=5,
        running_vms=3,
        total_containers=10,
        running_containers=8,
    )

    summary = info.get_summary()
    assert "PROXMOX VE SUMMARY" in summary
    assert "8.1.3" in summary
    assert "prod-cluster" in summary
    assert "pve1" in summary
    assert "5" in summary
    assert "3" in summary


@pytest.mark.asyncio
async def test_proxmox_info_non_proxmox_summary():
    """Test summary for non-Proxmox host."""
    info = ProxmoxInfo(
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        is_proxmox_host=False,
        version=None,
        cluster=None,
        nodes=[],
        virtual_machines=[],
        containers=[],
        storage_pools=[],
        network_interfaces=[],
    )

    summary = info.get_summary()
    assert "not a Proxmox VE host" in summary


def test_parse_storage_type():
    """Test storage type parsing."""
    assert ProxmoxCollector._parse_storage_type("dir") == StorageType.DIR
    assert ProxmoxCollector._parse_storage_type("lvm") == StorageType.LVM
    assert ProxmoxCollector._parse_storage_type("lvmthin") == StorageType.LVMTHIN
    assert ProxmoxCollector._parse_storage_type("zfs") == StorageType.ZFS
    assert ProxmoxCollector._parse_storage_type("nfs") == StorageType.NFS
    assert ProxmoxCollector._parse_storage_type("rbd") == StorageType.CEPH
    assert ProxmoxCollector._parse_storage_type("unknown") == StorageType.OTHER


def test_parse_content_types():
    """Test content type parsing."""
    types = ProxmoxCollector._parse_content_types("images,rootdir,backup")
    assert StorageContentType.IMAGES in types
    assert StorageContentType.ROOTDIR in types
    assert StorageContentType.BACKUP in types
    assert len(types) == 3


def test_parse_vm_status():
    """Test VM status parsing."""
    assert ProxmoxCollector._parse_vm_status("running") == VMStatus.RUNNING
    assert ProxmoxCollector._parse_vm_status("stopped") == VMStatus.STOPPED
    assert ProxmoxCollector._parse_vm_status("paused") == VMStatus.PAUSED
    assert ProxmoxCollector._parse_vm_status("unknown_status") == VMStatus.UNKNOWN


def test_parse_node_status():
    """Test node status parsing."""
    assert ProxmoxCollector._parse_node_status("online") == ProxmoxNodeStatus.ONLINE
    assert ProxmoxCollector._parse_node_status("offline") == ProxmoxNodeStatus.OFFLINE
    assert ProxmoxCollector._parse_node_status("something") == ProxmoxNodeStatus.UNKNOWN
