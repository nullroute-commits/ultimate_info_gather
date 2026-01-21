"""Tests for install_github_copilot.py filesystem operations."""
# Import the module under test
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from install_github_copilot import (
    DeviceCapabilities,
    DeviceCapabilityDetector,
    GitHubCopilotInstaller,
)


class TestFilesystemOperations:
    """Test cross-platform filesystem operations."""

    @pytest.mark.asyncio
    async def test_openwrt_detection_linux_only(self):
        """Test that OpenWrt detection only runs on Linux."""
        with patch('install_github_copilot.platform.system', return_value='Windows'):
            # On Windows, should return False without checking files
            result = await DeviceCapabilityDetector._check_openwrt()
            assert result is False

        with patch('install_github_copilot.platform.system', return_value='Darwin'):
            # On macOS, should return False without checking files
            result = await DeviceCapabilityDetector._check_openwrt()
            assert result is False

    @pytest.mark.asyncio
    async def test_available_space_windows(self):
        """Test disk space detection on Windows."""
        with patch('install_github_copilot.platform.system', return_value='Windows'):
            with patch('install_github_copilot.shutil.disk_usage') as mock_disk:
                mock_disk.return_value = MagicMock(free=100 * 1024 * 1024 * 1024)  # 100GB
                space = await DeviceCapabilityDetector._get_available_space()
                # Should have called disk_usage with SystemDrive on Windows
                assert space == 100 * 1024  # 100GB in MB

    @pytest.mark.asyncio
    async def test_available_space_linux(self):
        """Test disk space detection on Linux."""
        with patch('install_github_copilot.platform.system', return_value='Linux'):
            with patch('install_github_copilot.shutil.disk_usage') as mock_disk:
                mock_disk.return_value = MagicMock(free=50 * 1024 * 1024 * 1024)  # 50GB
                space = await DeviceCapabilityDetector._get_available_space()
                # Should have called disk_usage with / on Linux
                mock_disk.assert_called_once_with('/')
                assert space == 50 * 1024  # 50GB in MB

    def test_temp_dir_openwrt(self):
        """Test temp directory selection on OpenWrt."""
        caps = DeviceCapabilities(
            os_name="Linux",
            architecture="armv7l",
            package_manager="opkg",
            has_opkg=True,
            is_openwrt=True,
            available_space_mb=200,
            has_node=False,
            has_npm=False,
            has_git=False,
            has_curl=True,
            has_wget=False,
            has_gh=False,
            node_version=None,
            npm_version=None,
            gh_version=None,
        )
        installer = GitHubCopilotInstaller(caps)

        # On OpenWrt, should prefer /var/tmp if it has space
        with patch('install_github_copilot.Path.exists', return_value=True):
            with patch('install_github_copilot.shutil.disk_usage') as mock_disk:
                # /var/tmp has good space
                mock_disk.return_value = MagicMock(free=100 * 1024 * 1024)  # 100MB
                temp_dir = installer._get_temp_dir()
                assert str(temp_dir) == '/var/tmp'

    def test_temp_dir_standard_linux(self):
        """Test temp directory selection on standard Linux."""
        caps = DeviceCapabilities(
            os_name="Linux",
            architecture="x86_64",
            package_manager="apt",
            has_opkg=False,
            is_openwrt=False,
            available_space_mb=10000,
            has_node=False,
            has_npm=False,
            has_git=False,
            has_curl=True,
            has_wget=False,
            has_gh=False,
            node_version=None,
            npm_version=None,
            gh_version=None,
        )
        installer = GitHubCopilotInstaller(caps)

        # On standard Linux, should use tempfile.gettempdir()
        temp_dir = installer._get_temp_dir()
        expected = Path(tempfile.gettempdir())
        assert temp_dir == expected

    def test_temp_dir_windows(self):
        """Test temp directory selection on Windows."""
        caps = DeviceCapabilities(
            os_name="Windows",
            architecture="x86_64",
            package_manager=None,
            has_opkg=False,
            is_openwrt=False,
            available_space_mb=50000,
            has_node=False,
            has_npm=False,
            has_git=False,
            has_curl=False,
            has_wget=False,
            has_gh=False,
            node_version=None,
            npm_version=None,
            gh_version=None,
        )
        installer = GitHubCopilotInstaller(caps)

        # On Windows, should use standard tempfile.gettempdir()
        temp_dir = installer._get_temp_dir()
        expected = Path(tempfile.gettempdir())
        assert temp_dir == expected
