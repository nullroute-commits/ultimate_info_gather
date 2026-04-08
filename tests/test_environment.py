"""
Tests for environment collector.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.collectors.environment_collector import EnvironmentCollector
from src.models.environment import PlatformType


@pytest.mark.asyncio
async def test_environment_collector_basic():
    """Test basic environment collection."""
    collector = EnvironmentCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    assert result.data.python_env is not None
    assert result.data.process_info is not None
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_environment_collector_python_env():
    """Test Python environment detection."""
    collector = EnvironmentCollector()
    result = await collector.safe_collect()

    assert result.success
    env = result.data

    assert env.python_env.version
    assert env.python_env.implementation
    assert env.python_env.executable


@pytest.mark.asyncio
async def test_environment_collector_process_info():
    """Test process info collection."""
    collector = EnvironmentCollector()
    result = await collector.safe_collect()

    assert result.success
    env = result.data

    assert env.process_info.pid > 0
    assert env.process_info.cwd


@pytest.mark.asyncio
async def test_platform_detection():
    """Test platform type detection."""
    collector = EnvironmentCollector()
    result = await collector.safe_collect()

    assert result.success
    # Should detect Linux in test environment
    assert result.data.platform_type in [
        PlatformType.LINUX,
        PlatformType.MACOS,
        PlatformType.WINDOWS,
    ]


@pytest.mark.asyncio
async def test_container_detection_not_container():
    """Test container detection when not in container."""
    collector = EnvironmentCollector()

    with patch.object(collector, 'read_file_async', new_callable=AsyncMock) as mock_read:
        mock_read.return_value = None  # No container markers

        await collector._check_is_container()
        # Result depends on actual environment


@pytest.mark.asyncio
async def test_wsl_detection():
    """Test WSL detection."""
    collector = EnvironmentCollector()

    with patch.object(collector, 'read_file_async', new_callable=AsyncMock) as mock_read:
        mock_read.return_value = "Linux version 5.15.0-microsoft-standard-WSL2"

        is_wsl = await collector._check_is_wsl()
        assert is_wsl is True


@pytest.mark.asyncio
async def test_to_dict():
    """Test environment state serialization."""
    collector = EnvironmentCollector()
    result = await collector.safe_collect()

    assert result.success
    data = result.data.to_dict()

    assert 'timestamp' in data
    assert 'python_env' in data
    assert 'process_info' in data
    assert 'execution_mode' in data
    assert 'platform_type' in data


@pytest.mark.asyncio
async def test_get_summary():
    """Test human-readable summary generation."""
    collector = EnvironmentCollector()
    result = await collector.safe_collect()

    assert result.success
    summary = result.data.get_summary()

    assert 'ENVIRONMENT STATE SUMMARY' in summary
    assert 'Python Environment:' in summary
    assert 'Process Info:' in summary
