"""
Tests for improvements based on OpenWrt output analysis.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.collectors.base import BaseCollector
from src.collectors.hardware_collector import HardwareCollector
from src.collectors.software_collector import SoftwareCollector


@pytest.mark.asyncio
async def test_read_file_silent_if_missing():
    """Test that read_file_async can suppress warnings for missing files."""

    class TestCollector(BaseCollector):
        async def collect(self):
            return None

    collector = TestCollector()

    # Read a non-existent file with silent_if_missing=True
    result = await collector.read_file_async('/nonexistent/file/path', silent_if_missing=True)

    assert result is None
    assert len(collector._warnings) == 0  # No warnings should be added

    # Read a non-existent file with silent_if_missing=False (default)
    result = await collector.read_file_async('/nonexistent/file/path2', silent_if_missing=False)

    assert result is None
    assert len(collector._warnings) == 1  # Warning should be added
    assert '/nonexistent/file/path2' in collector._warnings[0]


@pytest.mark.asyncio
async def test_machine_id_missing_no_warning():
    """Test that missing machine-id doesn't generate warnings."""
    collector = HardwareCollector()

    with patch.object(collector, 'read_file_async', return_value=None) as mock_read:
        result = await collector._get_machine_id()

        # Should call with silent_if_missing=True
        mock_read.assert_called_once_with('/etc/machine-id', silent_if_missing=True)
        assert result is None


@pytest.mark.asyncio
async def test_product_uuid_missing_no_warning():
    """Test that missing product_uuid (ARM systems) doesn't generate warnings."""
    collector = HardwareCollector()

    with patch.object(collector, 'read_file_async', return_value=None) as mock_read:
        result = await collector._get_product_uuid()

        # Should call with silent_if_missing=True
        mock_read.assert_called_once_with('/sys/class/dmi/id/product_uuid', silent_if_missing=True)
        assert result is None


@pytest.mark.asyncio
async def test_opkg_package_manager_support():
    """Test that opkg (OpenWrt) package manager is supported."""
    collector = SoftwareCollector()

    # Mock opkg output
    opkg_output = """busybox - 1.35.0-4
base-files - 1519-r21859
"""

    with patch.object(collector, 'run_command', return_value=(0, opkg_output, '')) as mock_cmd:
        packages = await collector._get_installed_packages()

        # Should try opkg first
        mock_cmd.assert_called_once()
        call_args = mock_cmd.call_args[0][0]
        assert call_args == ['opkg', 'list-installed']

        # Should have parsed the packages
        assert len(packages) == 2
        assert packages[0].name == 'busybox'
        assert packages[0].version == '1.35.0-4'
        assert packages[0].package_manager == 'opkg'
        assert packages[1].name == 'base-files'


@pytest.mark.asyncio
async def test_opkg_in_package_managers_list():
    """Test that opkg is checked in package managers detection."""
    collector = SoftwareCollector()

    # Mock which command to return success for opkg
    async def mock_run_command(cmd, timeout):  # noqa: ARG001
        if cmd[0] == 'which' and cmd[1] == 'opkg':
            return (0, '/usr/bin/opkg', '')
        return (-1, '', 'not found')

    with patch.object(collector, 'run_command', side_effect=mock_run_command):
        managers = await collector._get_package_managers()

        assert 'opkg' in managers


@pytest.mark.asyncio
async def test_network_speed_read_error_handling():
    """Test that network interface speed reading handles errors gracefully."""
    collector = HardwareCollector()

    # Create a mock Path structure for network interfaces
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.iterdir', return_value=[Path('/sys/class/net/lo')]), \
         patch.object(collector, 'read_file_async') as mock_read, \
         patch.object(collector, '_get_ip_addresses', return_value=([], [])):

        # Mock the file reads for network interface
        def mock_read_side_effect(path, silent_if_missing=False):  # noqa: ARG001
            if 'address' in path:
                return '00:00:00:00:00:00'
            elif 'operstate' in path:
                return 'up'
            elif 'mtu' in path:
                return '65536'
            elif 'speed' in path:
                # Simulate OSError (EINVAL) for virtual interface
                return None
            return None

        mock_read.side_effect = mock_read_side_effect

        await collector._get_network_interfaces()

        # Should not have warnings about speed reading for virtual interfaces
        # The speed file read should have been called with silent_if_missing=True
        speed_calls = [call for call in mock_read.call_args_list if 'speed' in str(call)]
        if speed_calls:
            # Verify silent_if_missing was True
            assert speed_calls[0][1].get('silent_if_missing', False)
