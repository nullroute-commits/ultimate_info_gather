"""
Tests for the network collector with intensive in-depth network capabilities.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.collectors.network_collector import NetworkCollector
from src.models.network import (
    ConnectionState,
    Protocol,
    RouteType,
)


@pytest.mark.asyncio
async def test_network_collector_basic():
    """Test basic network collector initialization and collection."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    assert result.data.timestamp is not None


@pytest.mark.asyncio
async def test_network_collector_interfaces():
    """Test that network interfaces are collected."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    # Should have at least loopback interface
    assert len(result.data.interfaces) > 0

    # Check for loopback
    loopback = next((i for i in result.data.interfaces if i.name == 'lo'), None)
    if loopback:
        assert loopback.is_loopback
        assert loopback.is_virtual


@pytest.mark.asyncio
async def test_network_collector_interface_statistics():
    """Test that interface statistics are collected."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None

    # At least one interface should have statistics
    interfaces_with_stats = [i for i in result.data.interfaces if i.statistics]
    # Statistics are available on most systems
    if interfaces_with_stats:
        stats = interfaces_with_stats[0].statistics
        assert stats.rx_bytes >= 0
        assert stats.tx_bytes >= 0
        assert stats.rx_packets >= 0
        assert stats.tx_packets >= 0


@pytest.mark.asyncio
async def test_network_collector_dns_config():
    """Test that DNS configuration is collected."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None

    # DNS config should be present if /etc/resolv.conf exists
    if result.data.dns_config:
        assert result.data.dns_config.resolv_conf_path == '/etc/resolv.conf'
        # Nameservers list should exist (may be empty)
        assert isinstance(result.data.dns_config.nameservers, list)


@pytest.mark.asyncio
async def test_network_collector_routes():
    """Test that routing table is collected."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    # Should have at least some routes
    assert isinstance(result.data.routes, list)


@pytest.mark.asyncio
async def test_network_collector_connections():
    """Test that network connections are collected."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    # Should have connections list (may be empty)
    assert isinstance(result.data.connections, list)
    assert isinstance(result.data.listening_ports, list)


@pytest.mark.asyncio
async def test_network_collector_arp_table():
    """Test that ARP table is collected."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    # Should have ARP table list (may be empty)
    assert isinstance(result.data.arp_table, list)


@pytest.mark.asyncio
async def test_network_collector_to_dict():
    """Test that network info can be serialized to dict."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None

    data_dict = result.data.to_dict()
    assert 'timestamp' in data_dict
    assert 'interfaces' in data_dict
    assert 'routes' in data_dict
    assert 'dns_config' in data_dict
    assert 'arp_table' in data_dict
    assert 'connections' in data_dict
    assert 'listening_ports' in data_dict
    assert 'total_rx_bytes' in data_dict
    assert 'total_tx_bytes' in data_dict


@pytest.mark.asyncio
async def test_network_collector_get_summary():
    """Test that network summary is generated."""
    collector = NetworkCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None

    summary = result.data.get_summary()
    assert 'NETWORK SUMMARY' in summary
    assert 'Interfaces:' in summary
    assert 'Routing:' in summary


@pytest.mark.asyncio
async def test_parse_route():
    """Test route parsing."""
    collector = NetworkCollector()

    # Test default route
    route = collector._parse_route("default via 192.168.1.1 dev eth0 proto static metric 100")
    assert route is not None
    assert route.route_type == RouteType.DEFAULT
    assert route.gateway == "192.168.1.1"
    assert route.interface == "eth0"
    assert route.metric == 100

    # Test local route
    route = collector._parse_route("192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100")
    assert route is not None
    assert route.destination == "192.168.1.0"
    assert route.interface == "eth0"


@pytest.mark.asyncio
async def test_parse_connection_state():
    """Test connection state parsing."""
    collector = NetworkCollector()

    assert collector._parse_state("LISTEN") == ConnectionState.LISTEN
    assert collector._parse_state("ESTAB") == ConnectionState.ESTABLISHED
    assert collector._parse_state("ESTABLISHED") == ConnectionState.ESTABLISHED
    assert collector._parse_state("TIME-WAIT") == ConnectionState.TIME_WAIT
    assert collector._parse_state("CLOSE-WAIT") == ConnectionState.CLOSE_WAIT
    assert collector._parse_state("UNKNOWN") == ConnectionState.UNKNOWN


@pytest.mark.asyncio
async def test_parse_protocol():
    """Test protocol parsing."""
    collector = NetworkCollector()

    assert collector._parse_protocol("tcp") == Protocol.TCP
    assert collector._parse_protocol("tcp6") == Protocol.TCP6
    assert collector._parse_protocol("udp") == Protocol.UDP
    assert collector._parse_protocol("udp6") == Protocol.UDP6
    assert collector._parse_protocol("unknown") is None


@pytest.mark.asyncio
async def test_parse_address():
    """Test address parsing."""
    collector = NetworkCollector()

    # IPv4
    addr, port = collector._parse_address("192.168.1.1:22")
    assert addr == "192.168.1.1"
    assert port == 22

    # IPv4 wildcard
    addr, port = collector._parse_address("*:80")
    assert addr == "*"
    assert port == 80

    # IPv6 with brackets
    addr, port = collector._parse_address("[::1]:22")
    assert addr == "::1"
    assert port == 22


@pytest.mark.asyncio
async def test_prefix_to_netmask():
    """Test CIDR to netmask conversion."""
    collector = NetworkCollector()

    assert collector._prefix_to_netmask(24) == "255.255.255.0"
    assert collector._prefix_to_netmask(16) == "255.255.0.0"
    assert collector._prefix_to_netmask(8) == "255.0.0.0"
    assert collector._prefix_to_netmask(32) == "255.255.255.255"
    assert collector._prefix_to_netmask(0) == "0.0.0.0"


@pytest.mark.asyncio
async def test_get_service_name():
    """Test service name lookup."""
    collector = NetworkCollector()

    assert collector._get_service_name(22, "tcp") == "ssh"
    assert collector._get_service_name(80, "tcp") == "http"
    assert collector._get_service_name(443, "tcp") == "https"
    assert collector._get_service_name(53, "udp") == "dns"
    assert collector._get_service_name(12345, "tcp") is None


@pytest.mark.asyncio
async def test_network_collector_with_environment_state():
    """Test network collector with environment state."""
    from src.models.environment import (
        EnvironmentState,
        ExecutionMode,
        PlatformType,
        ProcessInfo,
        PythonEnvironment,
    )

    env_state = EnvironmentState(
        timestamp=datetime.now(),
        python_env=PythonEnvironment(
            version="3.11.0",
            version_info=(3, 11, 0, 'final', 0),
            implementation="cpython",
            executable="/usr/bin/python3.11",
            prefix="/usr",
            base_prefix="/usr",
            is_virtual_env=False,
            platform="linux",
            path=["/usr/lib/python311.zip"],
        ),
        process_info=ProcessInfo(
            pid=12345,
            ppid=1,
            uid=1000,
            gid=1000,
            euid=1000,
            egid=1000,
            cwd="/home/user",
            argv=["python", "main.py"],
        ),
        execution_mode=ExecutionMode.SCRIPT,
        platform_type=PlatformType.LINUX,
        environment_variables={"HOME": "/home/user"},
        hostname="testhost",
        is_root=False,
        is_container=False,
        is_wsl=False,
        terminal_type="xterm-256color",
        shell="/bin/bash",
        home_directory="/home/user",
        temp_directory="/tmp",
    )

    collector = NetworkCollector(environment_state=env_state)
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None


@pytest.mark.asyncio
async def test_network_info_in_orchestrator():
    """Test that network info is included in orchestrator collection."""
    from src.orchestrator import InfoGatherOrchestrator

    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()

    assert report is not None
    assert report.network is not None
    assert isinstance(report.network.interfaces, list)

    # Network should be in stored data
    stored = orchestrator.get_stored_data()
    assert 'network' in stored
    assert stored['network'] is not None


@pytest.mark.asyncio
async def test_network_in_report_dict():
    """Test that network info is in report dict."""
    from src.orchestrator import InfoGatherOrchestrator

    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()

    report_dict = report.to_dict()
    assert 'network' in report_dict
    if report_dict['network']:
        assert 'interfaces' in report_dict['network']
        assert 'routes' in report_dict['network']


@pytest.mark.asyncio
async def test_network_in_markdown_report():
    """Test that network info is in markdown report."""
    from src.orchestrator import InfoGatherOrchestrator

    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()

    markdown = report.get_markdown_report()
    assert '## 🌐 Network' in markdown
    assert '### Interfaces' in markdown
    assert '### Routing' in markdown


@pytest.mark.asyncio
async def test_network_in_text_summary():
    """Test that network info is in text summary."""
    from src.orchestrator import InfoGatherOrchestrator

    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()

    summary = report.get_full_summary()
    assert 'NETWORK SUMMARY' in summary
