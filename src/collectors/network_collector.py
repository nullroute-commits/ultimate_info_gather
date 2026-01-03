"""
Network collector - Intensive in-depth network capabilities.

Collects comprehensive network information including interfaces with statistics,
routing tables, DNS configuration, ARP tables, active connections, listening ports,
and firewall status.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..models.environment import EnvironmentState
from ..models.network import (
    ARPEntry,
    ConnectionState,
    DNSConfiguration,
    FirewallStatus,
    InterfaceStatistics,
    ListeningPort,
    NetworkConnection,
    NetworkInfo,
    NetworkInterfaceExtended,
    Protocol,
    Route,
    RouteType,
)
from ..models.permissions import PermissionsInfo
from .base import BaseCollector


class NetworkCollector(BaseCollector[NetworkInfo]):
    """
    Collects comprehensive network information.
    
    Provides intensive in-depth network analysis including:
    - Extended interface information with statistics
    - Routing tables
    - DNS configuration
    - ARP tables
    - Active network connections
    - Listening ports
    - Firewall status
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

    async def collect(self) -> NetworkInfo:
        """Collect comprehensive network information."""
        timestamp = datetime.now()

        # Collect all network info in parallel where possible
        (
            interfaces,
            routes,
            dns_config,
            arp_table,
            connections,
            listening_ports,
            firewall_status,
        ) = await self.gather_with_errors(
            self._get_interfaces(),
            self._get_routes(),
            self._get_dns_config(),
            self._get_arp_table(),
            self._get_connections(),
            self._get_listening_ports(),
            self._get_firewall_status(),
        )

        interfaces = interfaces or []
        routes = routes or []
        arp_table = arp_table or []
        connections = connections or []
        listening_ports = listening_ports or []

        # Calculate summary statistics
        total_rx = sum(
            i.statistics.rx_bytes for i in interfaces 
            if i.statistics and not i.is_loopback
        )
        total_tx = sum(
            i.statistics.tx_bytes for i in interfaces 
            if i.statistics and not i.is_loopback
        )

        # Determine default gateway and interface
        default_gateway = None
        default_interface = None
        for route in routes:
            if route.route_type == RouteType.DEFAULT:
                default_gateway = route.gateway
                default_interface = route.interface
                break

        active_connections = [
            c for c in connections 
            if c.state == ConnectionState.ESTABLISHED
        ]

        return NetworkInfo(
            timestamp=timestamp,
            interfaces=interfaces,
            routes=routes,
            default_gateway=default_gateway,
            default_interface=default_interface,
            dns_config=dns_config,
            arp_table=arp_table,
            connections=connections,
            listening_ports=listening_ports,
            firewall=firewall_status,
            total_rx_bytes=total_rx,
            total_tx_bytes=total_tx,
            active_connections_count=len(active_connections),
            listening_ports_count=len(listening_ports),
            errors=self._errors.copy(),
            warnings=self._warnings.copy(),
        )

    async def _get_interfaces(self) -> list[NetworkInterfaceExtended]:
        """Get extended network interface information."""
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
                        speed_content = (
                            await self.read_file_async(str(speed_file), silent_if_missing=True) or ''
                        ).strip()
                        if speed_content and speed_content != '-1':
                            speed = int(speed_content)
                    except (ValueError, OSError):
                        pass

                # Get duplex
                duplex_file = iface_dir / 'duplex'
                duplex = None
                if duplex_file.exists():
                    try:
                        duplex = (
                            await self.read_file_async(str(duplex_file), silent_if_missing=True) or ''
                        ).strip() or None
                    except OSError:
                        pass

                # Get carrier status
                carrier_file = iface_dir / 'carrier'
                carrier = False
                if carrier_file.exists():
                    try:
                        carrier_content = (
                            await self.read_file_async(str(carrier_file), silent_if_missing=True) or ''
                        ).strip()
                        carrier = carrier_content == '1'
                    except OSError:
                        pass

                # Get driver
                driver = None
                driver_link = iface_dir / 'device/driver'
                if driver_link.exists():
                    try:
                        driver_path = driver_link.resolve()
                        driver = driver_path.name
                    except (OSError, ValueError):
                        pass

                # Get interface statistics
                statistics = await self._get_interface_statistics(name)

                # Get IP addresses and additional info using ip command
                ipv4_addrs, ipv6_addrs, broadcast, netmask = await self._get_ip_details(name)

                # Get gateway for this interface
                gateway = await self._get_interface_gateway(name)

                # Get DNS servers (interface-specific if available via systemd-resolved)
                dns_servers = await self._get_interface_dns(name)

                interfaces.append(NetworkInterfaceExtended(
                    name=name,
                    mac_address=mac,
                    ipv4_addresses=ipv4_addrs,
                    ipv6_addresses=ipv6_addrs,
                    is_up=is_up,
                    is_loopback=is_loopback,
                    is_virtual=is_virtual,
                    speed_mbps=speed,
                    mtu=mtu,
                    driver=driver,
                    duplex=duplex,
                    carrier=carrier,
                    statistics=statistics,
                    broadcast_address=broadcast,
                    netmask=netmask,
                    gateway=gateway,
                    dns_servers=dns_servers,
                ))
        except Exception as e:
            self.add_warning(f"Failed to get network interfaces: {e}")

        return interfaces

    async def _get_interface_statistics(self, iface: str) -> InterfaceStatistics | None:
        """Get network interface statistics."""
        try:
            stats_path = Path(f'/sys/class/net/{iface}/statistics')
            if not stats_path.exists():
                return None

            async def read_stat(name: str) -> int:
                content = await self.read_file_async(str(stats_path / name), silent_if_missing=True)
                return int(content.strip()) if content else 0

            return InterfaceStatistics(
                rx_bytes=await read_stat('rx_bytes'),
                rx_packets=await read_stat('rx_packets'),
                rx_errors=await read_stat('rx_errors'),
                rx_dropped=await read_stat('rx_dropped'),
                tx_bytes=await read_stat('tx_bytes'),
                tx_packets=await read_stat('tx_packets'),
                tx_errors=await read_stat('tx_errors'),
                tx_dropped=await read_stat('tx_dropped'),
                collisions=await read_stat('collisions'),
            )
        except Exception as e:
            self.add_warning(f"Failed to get statistics for {iface}: {e}")
            return None

    async def _get_ip_details(
        self, iface: str
    ) -> tuple[list[str], list[str], str | None, str | None]:
        """Get detailed IP information for an interface."""
        ipv4_addrs = []
        ipv6_addrs = []
        broadcast = None
        netmask = None

        ret, stdout, _ = await self.run_command(['ip', 'addr', 'show', iface], timeout=5)
        if ret == 0 and stdout:
            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith('inet '):
                    parts = line.split()
                    if len(parts) >= 2:
                        addr_with_prefix = parts[1]
                        addr = addr_with_prefix.split('/')[0]
                        ipv4_addrs.append(addr)

                        # Extract netmask from prefix
                        if '/' in addr_with_prefix:
                            try:
                                prefix = int(addr_with_prefix.split('/')[1])
                                netmask = self._prefix_to_netmask(prefix)
                            except ValueError:
                                pass  # Invalid prefix, skip netmask extraction

                        # Extract broadcast
                        if 'brd' in parts:
                            brd_idx = parts.index('brd')
                            if brd_idx + 1 < len(parts):
                                broadcast = parts[brd_idx + 1]

                elif line.startswith('inet6 '):
                    parts = line.split()
                    if len(parts) >= 2:
                        ipv6_addrs.append(parts[1].split('/')[0])

        return ipv4_addrs, ipv6_addrs, broadcast, netmask

    def _prefix_to_netmask(self, prefix: int) -> str:
        """Convert CIDR prefix to dotted netmask."""
        if prefix < 0 or prefix > 32:
            return "255.255.255.255"
        mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
        return f"{(mask >> 24) & 0xFF}.{(mask >> 16) & 0xFF}.{(mask >> 8) & 0xFF}.{mask & 0xFF}"

    async def _get_interface_gateway(self, iface: str) -> str | None:
        """Get gateway for a specific interface."""
        ret, stdout, _ = await self.run_command(
            ['ip', 'route', 'show', 'dev', iface], timeout=5
        )
        if ret == 0 and stdout:
            for line in stdout.split('\n'):
                if 'default' in line and 'via' in line:
                    parts = line.split()
                    if 'via' in parts:
                        via_idx = parts.index('via')
                        if via_idx + 1 < len(parts):
                            return parts[via_idx + 1]
        return None

    async def _get_interface_dns(self, iface: str) -> list[str]:
        """Get DNS servers for a specific interface."""
        dns_servers = []

        # Try systemd-resolve for interface-specific DNS
        ret, stdout, _ = await self.run_command(
            ['resolvectl', 'dns', iface], timeout=5
        )
        if ret == 0 and stdout:
            # Parse: "Link 2 (eth0): 8.8.8.8 8.8.4.4"
            parts = stdout.strip().split(':')
            if len(parts) >= 2:
                dns_part = parts[-1].strip()
                dns_servers = [d.strip() for d in dns_part.split() if d.strip()]

        return dns_servers

    async def _get_routes(self) -> list[Route]:
        """Get routing table."""
        routes = []

        try:
            # Get IPv4 routes
            ret, stdout, _ = await self.run_command(['ip', 'route', 'show'], timeout=10)
            if ret == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    if not line:
                        continue
                    route = self._parse_route(line)
                    if route:
                        routes.append(route)

            # Get IPv6 routes
            ret6, stdout6, _ = await self.run_command(['ip', '-6', 'route', 'show'], timeout=10)
            if ret6 == 0 and stdout6:
                for line in stdout6.strip().split('\n'):
                    if not line:
                        continue
                    route = self._parse_route(line, is_ipv6=True)
                    if route:
                        routes.append(route)

        except Exception as e:
            self.add_warning(f"Failed to get routes: {e}")

        return routes

    def _parse_route(self, line: str, is_ipv6: bool = False) -> Route | None:
        """Parse a route line from ip route output."""
        parts = line.split()
        if not parts:
            return None

        destination = parts[0]
        gateway = None
        interface = ""
        metric = 0
        flags = []

        # Determine route type
        if destination == 'default':
            route_type = RouteType.DEFAULT
            destination = '::/0' if is_ipv6 else '0.0.0.0/0'
        elif 'linkdown' in line.lower():
            route_type = RouteType.STATIC
        else:
            route_type = RouteType.CONNECTED

        # Parse remaining fields
        i = 1
        while i < len(parts):
            if parts[i] == 'via':
                if i + 1 < len(parts):
                    gateway = parts[i + 1]
                    i += 2
                else:
                    i += 1
            elif parts[i] == 'dev':
                if i + 1 < len(parts):
                    interface = parts[i + 1]
                    i += 2
                else:
                    i += 1
            elif parts[i] == 'metric':
                if i + 1 < len(parts):
                    try:
                        metric = int(parts[i + 1])
                    except ValueError:
                        pass
                    i += 2
                else:
                    i += 1
            elif parts[i] in ('proto', 'scope', 'src'):
                if i + 1 < len(parts):
                    flags.append(f"{parts[i]}={parts[i + 1]}")
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        # Extract netmask from destination
        if '/' in destination:
            dest_parts = destination.split('/')
            netmask = dest_parts[1] if len(dest_parts) > 1 else '32'
        else:
            netmask = '128' if is_ipv6 else '32'

        return Route(
            destination=destination.split('/')[0] if '/' in destination else destination,
            gateway=gateway,
            netmask=netmask,
            interface=interface,
            metric=metric,
            route_type=route_type,
            flags=flags,
        )

    async def _get_dns_config(self) -> DNSConfiguration | None:
        """Get DNS configuration."""
        nameservers = []
        search_domains = []
        dns_options = []
        resolv_conf_path = '/etc/resolv.conf'

        try:
            content = await self.read_file_async(resolv_conf_path)
            if content:
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue

                    if line.startswith('nameserver'):
                        parts = line.split()
                        if len(parts) >= 2:
                            nameservers.append(parts[1])
                    elif line.startswith('search'):
                        parts = line.split()
                        search_domains.extend(parts[1:])
                    elif line.startswith('domain'):
                        parts = line.split()
                        if len(parts) >= 2:
                            search_domains.append(parts[1])
                    elif line.startswith('options'):
                        parts = line.split()
                        dns_options.extend(parts[1:])

            return DNSConfiguration(
                nameservers=nameservers,
                search_domains=search_domains,
                dns_options=dns_options,
                resolv_conf_path=resolv_conf_path,
            )
        except Exception as e:
            self.add_warning(f"Failed to get DNS config: {e}")
            return None

    async def _get_arp_table(self) -> list[ARPEntry]:
        """Get ARP table."""
        entries = []

        try:
            # Try ip neigh first (modern)
            ret, stdout, _ = await self.run_command(['ip', 'neigh', 'show'], timeout=10)
            if ret == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    if not line:
                        continue
                    entry = self._parse_ip_neigh(line)
                    if entry:
                        entries.append(entry)
            else:
                # Fall back to /proc/net/arp
                content = await self.read_file_async('/proc/net/arp')
                if content:
                    lines = content.strip().split('\n')
                    for line in lines[1:]:  # Skip header
                        parts = line.split()
                        if len(parts) >= 6:
                            entries.append(ARPEntry(
                                ip_address=parts[0],
                                mac_address=parts[3],
                                interface=parts[5],
                                flags=parts[2],
                                hw_type=parts[1],
                            ))
        except Exception as e:
            self.add_warning(f"Failed to get ARP table: {e}")

        return entries

    def _parse_ip_neigh(self, line: str) -> ARPEntry | None:
        """Parse ip neigh output line."""
        # Format: "192.168.1.1 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"
        parts = line.split()
        if len(parts) < 4:
            return None

        ip_address = parts[0]
        interface = ""
        mac_address = ""
        flags = ""

        i = 1
        while i < len(parts):
            if parts[i] == 'dev':
                if i + 1 < len(parts):
                    interface = parts[i + 1]
                    i += 2
                else:
                    i += 1
            elif parts[i] == 'lladdr':
                if i + 1 < len(parts):
                    mac_address = parts[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                # State flags like REACHABLE, STALE, etc.
                flags = parts[i]
                i += 1

        if not mac_address:
            return None

        return ARPEntry(
            ip_address=ip_address,
            mac_address=mac_address,
            interface=interface,
            flags=flags,
            hw_type="ether",
        )

    async def _get_connections(self) -> list[NetworkConnection]:
        """Get active network connections."""
        connections = []

        try:
            # Use ss command for better performance
            ret, stdout, _ = await self.run_command(
                ['ss', '-tunap', '--no-header'], timeout=15
            )
            if ret == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    if not line:
                        continue
                    conn = self._parse_ss_line(line)
                    if conn:
                        connections.append(conn)
            else:
                # Fall back to netstat
                ret, stdout, _ = await self.run_command(
                    ['netstat', '-tunap'], timeout=15
                )
                if ret == 0 and stdout:
                    for line in stdout.strip().split('\n'):
                        if line.startswith('tcp') or line.startswith('udp'):
                            conn = self._parse_netstat_line(line)
                            if conn:
                                connections.append(conn)
        except Exception as e:
            self.add_warning(f"Failed to get connections: {e}")

        return connections

    def _parse_ss_line(self, line: str) -> NetworkConnection | None:
        """Parse ss output line."""
        # Format: "tcp   ESTAB  0  0  192.168.1.100:22  192.168.1.1:54321  users:(("sshd",pid=1234,fd=3))"
        parts = line.split()
        if len(parts) < 5:
            return None

        proto_str = parts[0].lower()
        state_str = parts[1].upper()
        local = parts[4]
        remote = parts[5] if len(parts) > 5 else "*:*"

        # Parse protocol
        protocol = self._parse_protocol(proto_str)
        if not protocol:
            return None

        # Parse state
        state = self._parse_state(state_str)

        # Parse addresses
        local_addr, local_port = self._parse_address(local)
        remote_addr, remote_port = self._parse_address(remote)

        # Parse process info
        pid = None
        process_name = None
        if len(parts) > 6:
            proc_info = ' '.join(parts[6:])
            pid, process_name = self._parse_process_info(proc_info)

        return NetworkConnection(
            protocol=protocol,
            local_address=local_addr,
            local_port=local_port,
            remote_address=remote_addr if remote_addr != '*' else None,
            remote_port=remote_port if remote_port != 0 else None,
            state=state,
            pid=pid,
            process_name=process_name,
        )

    def _parse_netstat_line(self, line: str) -> NetworkConnection | None:
        """Parse netstat output line."""
        parts = line.split()
        if len(parts) < 5:
            return None

        proto_str = parts[0].lower()
        local = parts[3]
        remote = parts[4]
        state_str = parts[5].upper() if len(parts) > 5 else "UNKNOWN"

        # Parse protocol
        protocol = self._parse_protocol(proto_str)
        if not protocol:
            return None

        # Parse state
        state = self._parse_state(state_str)

        # Parse addresses
        local_addr, local_port = self._parse_address(local)
        remote_addr, remote_port = self._parse_address(remote)

        # Parse process info
        pid = None
        process_name = None
        if len(parts) > 6 and parts[6] != '-':
            pid, process_name = self._parse_process_info(parts[6])

        return NetworkConnection(
            protocol=protocol,
            local_address=local_addr,
            local_port=local_port,
            remote_address=remote_addr if remote_addr != '*' else None,
            remote_port=remote_port if remote_port != 0 else None,
            state=state,
            pid=pid,
            process_name=process_name,
        )

    def _parse_protocol(self, proto: str) -> Protocol | None:
        """Parse protocol string."""
        proto_map = {
            'tcp': Protocol.TCP,
            'tcp6': Protocol.TCP6,
            'udp': Protocol.UDP,
            'udp6': Protocol.UDP6,
            'icmp': Protocol.ICMP,
            'raw': Protocol.RAW,
        }
        return proto_map.get(proto)

    def _parse_state(self, state: str) -> ConnectionState:
        """Parse connection state string."""
        state_map = {
            'LISTEN': ConnectionState.LISTEN,
            'ESTAB': ConnectionState.ESTABLISHED,
            'ESTABLISHED': ConnectionState.ESTABLISHED,
            'TIME-WAIT': ConnectionState.TIME_WAIT,
            'TIME_WAIT': ConnectionState.TIME_WAIT,
            'CLOSE-WAIT': ConnectionState.CLOSE_WAIT,
            'CLOSE_WAIT': ConnectionState.CLOSE_WAIT,
            'SYN-SENT': ConnectionState.SYN_SENT,
            'SYN_SENT': ConnectionState.SYN_SENT,
            'SYN-RECV': ConnectionState.SYN_RECV,
            'SYN_RECV': ConnectionState.SYN_RECV,
            'FIN-WAIT-1': ConnectionState.FIN_WAIT1,
            'FIN_WAIT1': ConnectionState.FIN_WAIT1,
            'FIN-WAIT-2': ConnectionState.FIN_WAIT2,
            'FIN_WAIT2': ConnectionState.FIN_WAIT2,
            'CLOSING': ConnectionState.CLOSING,
            'LAST-ACK': ConnectionState.LAST_ACK,
            'LAST_ACK': ConnectionState.LAST_ACK,
            'CLOSED': ConnectionState.CLOSED,
            'UNCONN': ConnectionState.CLOSED,
        }
        return state_map.get(state, ConnectionState.UNKNOWN)

    def _parse_address(self, addr: str) -> tuple[str, int]:
        """Parse address:port string."""
        if addr == '*:*':
            return '*', 0

        # Handle IPv6 addresses
        if addr.startswith('['):
            # [::1]:22 format
            match = re.match(r'\[([^\]]+)\]:(\d+)', addr)
            if match:
                try:
                    return match.group(1), int(match.group(2))
                except ValueError:
                    return match.group(1), 0
        elif addr.count(':') > 1:
            # IPv6 without brackets - last colon separates port
            last_colon = addr.rfind(':')
            if last_colon > 0:
                try:
                    return addr[:last_colon], int(addr[last_colon + 1:])
                except ValueError:
                    return addr[:last_colon], 0

        # IPv4 or simple format
        if ':' in addr:
            parts = addr.rsplit(':', 1)
            port_str = parts[1]
            try:
                port = int(port_str)
            except ValueError:
                port = 0
            return parts[0], port

        return addr, 0

    def _parse_process_info(self, info: str) -> tuple[int | None, str | None]:
        """Parse process information from ss/netstat output."""
        pid = None
        process_name = None

        # ss format: users:(("sshd",pid=1234,fd=3))
        pid_match = re.search(r'pid=(\d+)', info)
        if pid_match:
            pid = int(pid_match.group(1))

        name_match = re.search(r'\("([^"]+)"', info)
        if name_match:
            process_name = name_match.group(1)

        # netstat format: 1234/sshd
        if not pid:
            slash_match = re.match(r'(\d+)/(.+)', info)
            if slash_match:
                pid = int(slash_match.group(1))
                process_name = slash_match.group(2)

        return pid, process_name

    async def _get_listening_ports(self) -> list[ListeningPort]:
        """Get listening ports."""
        listening = []

        try:
            ret, stdout, _ = await self.run_command(
                ['ss', '-tulnp', '--no-header'], timeout=15
            )
            if ret == 0 and stdout:
                for line in stdout.strip().split('\n'):
                    if not line:
                        continue
                    port_info = self._parse_listening_port(line)
                    if port_info:
                        listening.append(port_info)
        except Exception as e:
            self.add_warning(f"Failed to get listening ports: {e}")

        return listening

    def _parse_listening_port(self, line: str) -> ListeningPort | None:
        """Parse ss listening port output."""
        parts = line.split()
        if len(parts) < 5:
            return None

        proto_str = parts[0].lower()
        local = parts[4]

        protocol = self._parse_protocol(proto_str)
        if not protocol:
            return None

        addr, port = self._parse_address(local)

        # Parse process info
        pid = None
        process_name = None
        if len(parts) > 6:
            proc_info = ' '.join(parts[6:])
            pid, process_name = self._parse_process_info(proc_info)

        # Try to get service name
        service_name = self._get_service_name(port, proto_str)

        return ListeningPort(
            protocol=protocol,
            address=addr,
            port=port,
            pid=pid,
            process_name=process_name,
            service_name=service_name,
        )

    def _get_service_name(self, port: int, protocol: str) -> str | None:
        """Get service name for a port."""
        # Common services
        services = {
            22: 'ssh',
            23: 'telnet',
            25: 'smtp',
            53: 'dns',
            80: 'http',
            110: 'pop3',
            143: 'imap',
            443: 'https',
            993: 'imaps',
            995: 'pop3s',
            3306: 'mysql',
            5432: 'postgresql',
            6379: 'redis',
            8080: 'http-alt',
            27017: 'mongodb',
        }
        return services.get(port)

    async def _get_firewall_status(self) -> FirewallStatus | None:
        """Get firewall status."""
        try:
            # Try nftables first (modern)
            ret, stdout, _ = await self.run_command(['nft', 'list', 'ruleset'], timeout=10)
            if ret == 0:
                rules_count = stdout.count('rule')
                return FirewallStatus(
                    enabled=rules_count > 0,
                    firewall_type='nftables',
                    default_input_policy=None,
                    default_output_policy=None,
                    default_forward_policy=None,
                    rules_count=rules_count,
                    active_zones=[],
                )

            # Try iptables
            ret, stdout, _ = await self.run_command(['iptables', '-L', '-n'], timeout=10)
            if ret == 0:
                policies = self._parse_iptables_policies(stdout)
                # iptables output has 6 header lines:
                # 3 chains (INPUT, FORWARD, OUTPUT) x 2 lines each (Chain header + column headers)
                iptables_header_lines = 6
                rules_count = stdout.count('\n') - iptables_header_lines
                return FirewallStatus(
                    enabled=rules_count > 0,
                    firewall_type='iptables',
                    default_input_policy=policies.get('INPUT'),
                    default_output_policy=policies.get('OUTPUT'),
                    default_forward_policy=policies.get('FORWARD'),
                    rules_count=max(0, rules_count),
                    active_zones=[],
                )

            # Try ufw
            ret, stdout, _ = await self.run_command(['ufw', 'status'], timeout=10)
            if ret == 0:
                enabled = 'active' in stdout.lower()
                # ufw status output has ~4 header lines before rules
                ufw_header_lines = 4
                rules_count = stdout.count('\n') - ufw_header_lines if enabled else 0
                return FirewallStatus(
                    enabled=enabled,
                    firewall_type='ufw',
                    default_input_policy=None,
                    default_output_policy=None,
                    default_forward_policy=None,
                    rules_count=max(0, rules_count),
                    active_zones=[],
                )

            # Try firewalld
            ret, stdout, _ = await self.run_command(['firewall-cmd', '--state'], timeout=10)
            if ret == 0:
                enabled = 'running' in stdout.lower()
                zones = []
                if enabled:
                    ret2, zones_out, _ = await self.run_command(
                        ['firewall-cmd', '--get-active-zones'], timeout=10
                    )
                    if ret2 == 0:
                        zones = [z for z in zones_out.split('\n') if z and not z.startswith(' ')]

                return FirewallStatus(
                    enabled=enabled,
                    firewall_type='firewalld',
                    default_input_policy=None,
                    default_output_policy=None,
                    default_forward_policy=None,
                    rules_count=0,
                    active_zones=zones,
                )

        except Exception as e:
            self.add_warning(f"Failed to get firewall status: {e}")

        return None

    def _parse_iptables_policies(self, output: str) -> dict[str, str]:
        """Parse iptables chain policies."""
        policies = {}
        for line in output.split('\n'):
            if line.startswith('Chain'):
                parts = line.split()
                if len(parts) >= 4 and parts[2] == '(policy':
                    chain = parts[1]
                    policy = parts[3].rstrip(')')
                    policies[chain] = policy
        return policies
