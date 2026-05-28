# Proxmox VE Collection

The Proxmox collector gathers comprehensive information from Proxmox VE hosts, including cluster status, node details, virtual machines, containers, storage pools, and network configuration.

## Detection

The collector automatically detects whether the current system is a Proxmox VE host by checking for:

- `/etc/pve` directory (Proxmox cluster filesystem - pmxcfs)
- `/usr/bin/pvesh` binary
- `pveversion` command availability

If the system is not a Proxmox host, the collector returns `is_proxmox_host=False` with empty collections.

## ProxmoxInfo Model

```python
@dataclass
class ProxmoxInfo:
    timestamp: datetime
    is_proxmox_host: bool
    version: ProxmoxVersion | None
    cluster: ProxmoxClusterInfo | None
    nodes: list[ProxmoxNodeInfo]
    virtual_machines: list[ProxmoxVM]
    containers: list[ProxmoxContainer]
    storage_pools: list[ProxmoxStorage]
    network_interfaces: list[ProxmoxNetworkInterface]
    total_vms: int
    running_vms: int
    total_containers: int
    running_containers: int
    total_storage_bytes: int
    used_storage_bytes: int
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
```

## Data Collection Method

The collector uses `pvesh` (Proxmox VE Shell) to query the local REST API without needing authentication tokens. This provides access to the full Proxmox API from the command line.

### API Endpoints Used

| Endpoint | Data Collected |
|----------|---------------|
| `/version` | PVE version, release, kernel |
| `/cluster/status` | Cluster name, quorum, node count |
| `/nodes` | Node list with CPU/memory/disk stats |
| `/nodes/{node}/status` | Detailed node info (CPU model, swap, kernel) |
| `/nodes/{node}/network` | Network interfaces (bridges, bonds, VLANs) |
| `/cluster/resources?type=vm` | All VMs and containers across cluster |
| `/cluster/resources?type=storage` | Storage pool usage |
| `/storage` | Storage pool configuration |

## Version Information

| Field | Description |
|-------|-------------|
| `version` | PVE version (e.g., "8.1.3") |
| `release` | Release number |
| `repo_id` | Repository commit ID |
| `kernel_version` | Running kernel version |

## Cluster Information

| Field | Description |
|-------|-------------|
| `name` | Cluster name |
| `version` | Cluster configuration version |
| `nodes_count` | Number of nodes in the cluster |
| `quorate` | Whether the cluster has quorum |
| `cluster_id` | Unique cluster identifier |

## Node Details

Each node in the cluster includes:

| Field | Description |
|-------|-------------|
| `name` | Node hostname |
| `status` | ONLINE, OFFLINE, or UNKNOWN |
| `cpu_count` | Total CPU cores |
| `cpu_usage_percent` | Current CPU utilization |
| `memory_total_bytes` | Total RAM |
| `memory_used_bytes` | Used RAM |
| `memory_free_bytes` | Free RAM |
| `swap_total_bytes` | Total swap |
| `swap_used_bytes` | Used swap |
| `uptime_seconds` | Node uptime |
| `kernel_version` | Running kernel |
| `pve_version` | PVE manager version string |
| `cpu_model` | CPU model name |
| `local_disk_total_bytes` | Local disk total |
| `local_disk_used_bytes` | Local disk used |

## Virtual Machines (QEMU)

| Field | Description |
|-------|-------------|
| `vmid` | VM ID number |
| `name` | VM name |
| `status` | RUNNING, STOPPED, PAUSED, SUSPENDED |
| `node` | Host node |
| `cpu_cores` | Allocated CPU cores |
| `cpu_usage_percent` | Current CPU usage |
| `memory_max_bytes` | Allocated memory |
| `memory_used_bytes` | Currently used memory |
| `disk_total_bytes` | Total disk allocation |
| `disk_used_bytes` | Currently used disk |
| `uptime_seconds` | VM uptime |
| `template` | Whether this is a template |
| `tags` | Assigned tags |
| `ha_state` | High-availability state |
| `agent_running` | Whether QEMU guest agent is active |

## LXC Containers

| Field | Description |
|-------|-------------|
| `vmid` | Container ID number |
| `name` | Container name |
| `status` | RUNNING, STOPPED, PAUSED, SUSPENDED |
| `node` | Host node |
| `cpu_cores` | Allocated CPU cores |
| `cpu_usage_percent` | Current CPU usage |
| `memory_max_bytes` | Allocated memory |
| `memory_used_bytes` | Currently used memory |
| `disk_total_bytes` | Total disk allocation |
| `disk_used_bytes` | Currently used disk |
| `swap_total_bytes` | Allocated swap |
| `swap_used_bytes` | Used swap |
| `uptime_seconds` | Container uptime |
| `template` | Whether this is a template |
| `tags` | Assigned tags |
| `ha_state` | High-availability state |

## Storage Pools

| Field | Description |
|-------|-------------|
| `storage_id` | Storage identifier |
| `node` | Associated node (if not shared) |
| `storage_type` | DIR, LVM, LVMTHIN, ZFS, NFS, CIFS, ISCSI, CEPH, PBS |
| `content_types` | Supported content (IMAGES, ROOTDIR, VZTMPL, BACKUP, ISO, SNIPPETS) |
| `total_bytes` | Total capacity |
| `used_bytes` | Used space |
| `available_bytes` | Available space |
| `enabled` | Whether storage is enabled |
| `shared` | Whether storage is shared across nodes |
| `path` | Filesystem path (for local storage) |

## Network Interfaces

Proxmox-managed network configuration:

| Field | Description |
|-------|-------------|
| `iface` | Interface name (vmbr0, bond0, etc.) |
| `interface_type` | bridge, bond, eth, vlan, OVSBridge |
| `address` | IP address |
| `netmask` | Network mask |
| `gateway` | Default gateway |
| `bridge_ports` | Ports in the bridge |
| `bond_slaves` | Interfaces in the bond |
| `vlan_id` | VLAN tag ID |
| `active` | Whether interface is active |
| `autostart` | Whether interface starts on boot |
| `comments` | Configuration comments |

## Requirements

- The system must be a Proxmox VE host
- `pvesh` must be available (included in standard PVE installation)
- Root or appropriate permissions to query the API
- For cluster information, the node must be part of a cluster

## Example Output

```json
{
  "is_proxmox_host": true,
  "version": {
    "version": "8.1.3",
    "release": "1",
    "kernel_version": "6.5.13-3-pve"
  },
  "cluster": {
    "name": "production",
    "nodes_count": 3,
    "quorate": true
  },
  "nodes": [...],
  "total_vms": 25,
  "running_vms": 20,
  "total_containers": 15,
  "running_containers": 12,
  "total_storage_bytes": 10737418240000,
  "used_storage_bytes": 5368709120000
}
```

## References

- [Proxmox VE API Documentation](https://pve.proxmox.com/pve-docs/api-viewer/)
- [Proxmox VE Administration Guide](https://pve.proxmox.com/pve-docs/pve-admin-guide.html)
- [pvesh CLI Reference](https://pve.proxmox.com/pve-docs/pvesh.1.html)
- [Proxmox Cluster Manager](https://pve.proxmox.com/pve-docs/chapter-pvecm.html)
- [Proxmox Storage](https://pve.proxmox.com/pve-docs/chapter-pvesm.html)
