# Network Analysis

The network collector provides intensive in-depth analysis of network capabilities, interfaces, connections, routing, DNS, and firewall configuration.

## NetworkInfo Model

```python
@dataclass
class NetworkInfo:
    timestamp: datetime
    interfaces: list[NetworkInterfaceExtended]
    routes: list[Route]
    default_gateway: str | None
    default_interface: str | None
    dns_config: DNSConfiguration | None
    arp_table: list[ARPEntry]
    connections: list[NetworkConnection]
    listening_ports: list[ListeningPort]
    firewall: FirewallStatus | None
    total_rx_bytes: int
    total_tx_bytes: int
    active_connections_count: int
    listening_ports_count: int
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

The serialized report also includes `collection_duration_ms`, `errors`, and
`warnings` for the network collection phase.

## Network Interfaces

Each interface includes extended information:

| Field | Description |
|-------|-------------|
| `name` | Interface name (eth0, br-lan, etc.) |
| `mac_address` | Hardware MAC address |
| `ipv4_addresses` | List of IPv4 addresses |
| `ipv6_addresses` | List of IPv6 addresses |
| `is_up` | Operational state |
| `is_loopback` | Loopback interface flag |
| `is_virtual` | Virtual interface flag |
| `speed_mbps` | Link speed in Mbps (null for virtual) |
| `mtu` | Maximum Transmission Unit |
| `driver` | Kernel driver in use |
| `duplex` | Full/half duplex mode |
| `carrier` | Physical carrier detected |
| `statistics` | RX/TX packet and byte counts |
| `broadcast_address` | Broadcast address |
| `netmask` | Subnet mask |
| `gateway` | Default gateway for this interface |
| `dns_servers` | DNS servers for this interface |

## Interface Statistics

Per-interface traffic statistics:

| Field | Description |
|-------|-------------|
| `rx_bytes` | Total bytes received |
| `rx_packets` | Total packets received |
| `rx_errors` | Receive errors |
| `rx_dropped` | Dropped receive packets |
| `tx_bytes` | Total bytes transmitted |
| `tx_packets` | Total packets transmitted |
| `tx_errors` | Transmit errors |
| `tx_dropped` | Dropped transmit packets |
| `collisions` | Collision count |

## Routing Table

| Field | Description |
|-------|-------------|
| `destination` | Destination network |
| `gateway` | Next-hop gateway |
| `netmask` | Destination netmask |
| `interface` | Outbound interface |
| `metric` | Route metric/cost |
| `route_type` | DEFAULT, LOCAL, STATIC, DYNAMIC, CONNECTED |
| `flags` | Route flags |

## DNS Configuration

| Field | Description |
|-------|-------------|
| `nameservers` | DNS server IP addresses |
| `search_domains` | Search domains |
| `dns_options` | Resolver options |
| `resolv_conf_path` | Path to resolv.conf |

## Network Connections

Active TCP/UDP connections:

| Field | Description |
|-------|-------------|
| `protocol` | TCP, UDP, TCP6, UDP6 |
| `local_address` | Local IP address |
| `local_port` | Local port number |
| `remote_address` | Remote IP address |
| `remote_port` | Remote port number |
| `state` | LISTEN, ESTABLISHED, TIME_WAIT, etc. |
| `pid` | Process ID owning the socket |
| `process_name` | Process name |

## Listening Ports

| Field | Description |
|-------|-------------|
| `protocol` | TCP or UDP |
| `address` | Bound address |
| `port` | Port number |
| `pid` | Process ID |
| `process_name` | Process name |
| `service_name` | Well-known service name |

## Firewall Status

| Field | Description |
|-------|-------------|
| `enabled` | Firewall is active |
| `firewall_type` | iptables, nftables, ufw, firewalld |
| `default_input_policy` | Default INPUT chain policy |
| `default_output_policy` | Default OUTPUT chain policy |
| `default_forward_policy` | Default FORWARD chain policy |
| `rules_count` | Total number of rules |
| `active_zones` | Active firewalld zones |

## ARP Table

| Field | Description |
|-------|-------------|
| `ip_address` | IP address |
| `mac_address` | Hardware address |
| `interface` | Network interface |
| `flags` | ARP flags |
| `hw_type` | Hardware type |

## Usage Example

```python
from src.collectors import NetworkCollector

async def analyze_network():
    collector = NetworkCollector()
    result = await collector.safe_collect()

    if result.success:
        net = result.data

        print("Network Interfaces:")
        for iface in net.interfaces:
            status = "UP" if iface.is_up else "DOWN"
            ips = ", ".join(iface.ipv4_addresses) or "no IP"
            print(f"  {iface.name}: {status} - {ips}")
            if iface.speed_mbps:
                print(f"    Speed: {iface.speed_mbps} Mbps")

        print(f"\nDefault Gateway: {net.default_gateway}")

        if net.dns_config:
            print(f"DNS Servers: {', '.join(net.dns_config.nameservers)}")

        print(f"\nActive Connections: {net.active_connections_count}")
        print(f"Listening Ports: {net.listening_ports_count}")

        if net.firewall:
            status = "Enabled" if net.firewall.enabled else "Disabled"
            print(f"\nFirewall: {status} ({net.firewall.firewall_type})")
            print(f"  Rules: {net.firewall.rules_count}")

        total_rx_mb = net.total_rx_bytes / (1024 * 1024)
        total_tx_mb = net.total_tx_bytes / (1024 * 1024)
        print(f"\nTotal Traffic: RX {total_rx_mb:.2f} MB, TX {total_tx_mb:.2f} MB")
```

## Embedded Systems Notes

On embedded systems (e.g., OpenWrt), the network collector handles:

- **Virtual interfaces**: Speed reading returns `null` for bridge (`br-*`), VPN (`wg*`, `tun*`), and VLAN interfaces — this is expected behavior
- **Many interfaces**: Routers often have 10+ interfaces (eth, br-lan, wlan, wg)
- **OpenWrt-specific**: UCI configuration is not parsed, but IP/route info from kernel is available
- **Optional sysfs statistics**: missing or unsupported per-interface files are treated as non-fatal, so collection still succeeds on constrained or unusual kernels

See [Embedded Systems Guide](embedded-systems.md) for more details.
