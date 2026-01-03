"""
Network information data model.

Captures comprehensive network details including interfaces, connections,
routing, DNS, ARP, and firewall information for intensive in-depth analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class ConnectionState(Enum):
    """TCP/UDP connection state."""
    LISTEN = auto()
    ESTABLISHED = auto()
    TIME_WAIT = auto()
    CLOSE_WAIT = auto()
    SYN_SENT = auto()
    SYN_RECV = auto()
    FIN_WAIT1 = auto()
    FIN_WAIT2 = auto()
    CLOSING = auto()
    LAST_ACK = auto()
    CLOSED = auto()
    UNKNOWN = auto()


class Protocol(Enum):
    """Network protocol."""
    TCP = auto()
    UDP = auto()
    TCP6 = auto()
    UDP6 = auto()
    ICMP = auto()
    RAW = auto()


class RouteType(Enum):
    """Route type classification."""
    DEFAULT = auto()
    LOCAL = auto()
    STATIC = auto()
    DYNAMIC = auto()
    CONNECTED = auto()


@dataclass
class InterfaceStatistics:
    """
    Network interface statistics from /sys/class/net/<iface>/statistics.
    
    Attributes:
        rx_bytes: Total bytes received on the interface.
        rx_packets: Total packets received on the interface.
        rx_errors: Number of receive errors detected.
        rx_dropped: Number of received packets dropped.
        tx_bytes: Total bytes transmitted on the interface.
        tx_packets: Total packets transmitted on the interface.
        tx_errors: Number of transmission errors detected.
        tx_dropped: Number of transmitted packets dropped.
        collisions: Number of collisions detected on the interface.
    """
    rx_bytes: int
    rx_packets: int
    rx_errors: int
    rx_dropped: int
    tx_bytes: int
    tx_packets: int
    tx_errors: int
    tx_dropped: int
    collisions: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rx_bytes": self.rx_bytes,
            "rx_packets": self.rx_packets,
            "rx_errors": self.rx_errors,
            "rx_dropped": self.rx_dropped,
            "tx_bytes": self.tx_bytes,
            "tx_packets": self.tx_packets,
            "tx_errors": self.tx_errors,
            "tx_dropped": self.tx_dropped,
            "collisions": self.collisions,
        }


@dataclass
class NetworkInterfaceExtended:
    """Extended network interface information with statistics."""
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
    duplex: str | None
    carrier: bool
    statistics: InterfaceStatistics | None
    # Extended fields
    broadcast_address: str | None
    netmask: str | None
    gateway: str | None
    dns_servers: list[str]

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
            "duplex": self.duplex,
            "carrier": self.carrier,
            "statistics": self.statistics.to_dict() if self.statistics else None,
            "broadcast_address": self.broadcast_address,
            "netmask": self.netmask,
            "gateway": self.gateway,
            "dns_servers": self.dns_servers,
        }


@dataclass
class Route:
    """Network routing table entry."""
    destination: str
    gateway: str | None
    netmask: str
    interface: str
    metric: int
    route_type: RouteType
    flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "destination": self.destination,
            "gateway": self.gateway,
            "netmask": self.netmask,
            "interface": self.interface,
            "metric": self.metric,
            "route_type": self.route_type.name,
            "flags": self.flags,
        }


@dataclass
class DNSConfiguration:
    """DNS configuration information."""
    nameservers: list[str]
    search_domains: list[str]
    dns_options: list[str]
    resolv_conf_path: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "nameservers": self.nameservers,
            "search_domains": self.search_domains,
            "dns_options": self.dns_options,
            "resolv_conf_path": self.resolv_conf_path,
        }


@dataclass
class ARPEntry:
    """ARP table entry."""
    ip_address: str
    mac_address: str
    interface: str
    flags: str
    hw_type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "interface": self.interface,
            "flags": self.flags,
            "hw_type": self.hw_type,
        }


@dataclass
class NetworkConnection:
    """Network connection (TCP/UDP socket)."""
    protocol: Protocol
    local_address: str
    local_port: int
    remote_address: str | None
    remote_port: int | None
    state: ConnectionState
    pid: int | None
    process_name: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "protocol": self.protocol.name,
            "local_address": self.local_address,
            "local_port": self.local_port,
            "remote_address": self.remote_address,
            "remote_port": self.remote_port,
            "state": self.state.name,
            "pid": self.pid,
            "process_name": self.process_name,
        }


@dataclass
class ListeningPort:
    """Listening port information."""
    protocol: Protocol
    address: str
    port: int
    pid: int | None
    process_name: str | None
    service_name: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "protocol": self.protocol.name,
            "address": self.address,
            "port": self.port,
            "pid": self.pid,
            "process_name": self.process_name,
            "service_name": self.service_name,
        }


@dataclass
class FirewallStatus:
    """Firewall status information."""
    enabled: bool
    firewall_type: str  # iptables, nftables, ufw, firewalld
    default_input_policy: str | None
    default_output_policy: str | None
    default_forward_policy: str | None
    rules_count: int
    active_zones: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "firewall_type": self.firewall_type,
            "default_input_policy": self.default_input_policy,
            "default_output_policy": self.default_output_policy,
            "default_forward_policy": self.default_forward_policy,
            "rules_count": self.rules_count,
            "active_zones": self.active_zones,
        }


@dataclass
class NetworkInfo:
    """
    Comprehensive network information collection.
    
    Provides intensive in-depth network analysis with interfaces,
    routing, DNS, ARP, connections, and firewall information.
    """
    timestamp: datetime

    # Network interfaces with extended information
    interfaces: list[NetworkInterfaceExtended]

    # Routing information
    routes: list[Route]
    default_gateway: str | None
    default_interface: str | None

    # DNS configuration
    dns_config: DNSConfiguration | None

    # ARP table
    arp_table: list[ARPEntry]

    # Network connections
    connections: list[NetworkConnection]
    listening_ports: list[ListeningPort]

    # Firewall status
    firewall: FirewallStatus | None

    # Summary statistics
    total_rx_bytes: int
    total_tx_bytes: int
    active_connections_count: int
    listening_ports_count: int

    # Metadata
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "interfaces": [i.to_dict() for i in self.interfaces],
            "routes": [r.to_dict() for r in self.routes],
            "default_gateway": self.default_gateway,
            "default_interface": self.default_interface,
            "dns_config": self.dns_config.to_dict() if self.dns_config else None,
            "arp_table": [a.to_dict() for a in self.arp_table],
            "connections": [c.to_dict() for c in self.connections],
            "listening_ports": [p.to_dict() for p in self.listening_ports],
            "firewall": self.firewall.to_dict() if self.firewall else None,
            "total_rx_bytes": self.total_rx_bytes,
            "total_tx_bytes": self.total_tx_bytes,
            "active_connections_count": self.active_connections_count,
            "listening_ports_count": self.listening_ports_count,
            "collection_duration_ms": self.collection_duration_ms,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            "=" * 60,
            "NETWORK SUMMARY",
            "=" * 60,
            f"Timestamp: {self.timestamp.isoformat()}",
            "",
            "Interfaces:",
        ]

        for iface in self.interfaces:
            status = "UP" if iface.is_up else "DOWN"
            ips = ", ".join(iface.ipv4_addresses) if iface.ipv4_addresses else "no IP"
            lines.append(f"  {iface.name}: {status} - {ips}")
            if iface.statistics:
                rx_mb = iface.statistics.rx_bytes / (1024 * 1024)
                tx_mb = iface.statistics.tx_bytes / (1024 * 1024)
                lines.append(f"    RX: {rx_mb:.2f} MB, TX: {tx_mb:.2f} MB")

        lines.extend([
            "",
            "Routing:",
            f"  Default Gateway: {self.default_gateway or 'None'}",
            f"  Default Interface: {self.default_interface or 'None'}",
            f"  Total Routes: {len(self.routes)}",
            "",
        ])

        if self.dns_config:
            lines.extend([
                "DNS Configuration:",
                f"  Nameservers: {', '.join(self.dns_config.nameservers) or 'None'}",
                f"  Search Domains: {', '.join(self.dns_config.search_domains) or 'None'}",
                "",
            ])

        lines.extend([
            "Connections:",
            f"  Active Connections: {self.active_connections_count}",
            f"  Listening Ports: {self.listening_ports_count}",
            "",
        ])

        if self.firewall:
            status = "Enabled" if self.firewall.enabled else "Disabled"
            lines.extend([
                "Firewall:",
                f"  Status: {status}",
                f"  Type: {self.firewall.firewall_type}",
                f"  Rules: {self.firewall.rules_count}",
                "",
            ])

        total_rx_mb = self.total_rx_bytes / (1024 * 1024)
        total_tx_mb = self.total_tx_bytes / (1024 * 1024)
        lines.extend([
            "Traffic Summary:",
            f"  Total RX: {total_rx_mb:.2f} MB",
            f"  Total TX: {total_tx_mb:.2f} MB",
            "",
        ])

        lines.append("=" * 60)
        return "\n".join(lines)
