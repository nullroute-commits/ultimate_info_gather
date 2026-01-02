"""
Tests for permissions collector.
"""


import pytest

from src.collectors.permissions_collector import PermissionsCollector
from src.models.permissions import PermissionLevel


@pytest.mark.asyncio
async def test_permissions_collector_basic():
    """Test basic permissions collection."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None
    assert result.data.permission_level is not None
    assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_permissions_with_environment_state(mock_environment_state):
    """Test permissions collection with prior environment state."""
    collector = PermissionsCollector(environment_state=mock_environment_state)
    result = await collector.safe_collect()

    assert result.success
    assert result.data is not None


@pytest.mark.asyncio
async def test_user_info_collection():
    """Test user information collection."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    perms = result.data

    assert perms.user_id is not None
    assert perms.user_name is not None


@pytest.mark.asyncio
async def test_group_collection():
    """Test group membership collection."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    perms = result.data

    assert isinstance(perms.groups, list)
    # Should have at least the primary group
    assert len(perms.groups) >= 0


@pytest.mark.asyncio
async def test_permission_level_detection():
    """Test permission level classification."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    assert result.data.permission_level in list(PermissionLevel)


@pytest.mark.asyncio
async def test_fs_permissions():
    """Test filesystem permission checks."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    perms = result.data

    assert isinstance(perms.fs_permissions, dict)
    # Should check critical paths
    assert len(perms.fs_permissions) > 0


@pytest.mark.asyncio
async def test_capabilities_collection():
    """Test Linux capabilities collection."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    perms = result.data

    assert isinstance(perms.capabilities, list)


@pytest.mark.asyncio
async def test_resources_collection():
    """Test resource information collection."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    perms = result.data

    assert perms.resources is not None
    assert perms.resources.cpu_count > 0
    assert perms.resources.memory_total_bytes > 0


@pytest.mark.asyncio
async def test_to_dict():
    """Test permissions info serialization."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    data = result.data.to_dict()

    assert 'timestamp' in data
    assert 'permission_level' in data
    assert 'user_id' in data
    assert 'groups' in data


@pytest.mark.asyncio
async def test_get_summary():
    """Test human-readable summary generation."""
    collector = PermissionsCollector()
    result = await collector.safe_collect()

    assert result.success
    summary = result.data.get_summary()

    assert 'PERMISSIONS SUMMARY' in summary
    assert 'Permission Level:' in summary
    assert 'User:' in summary
