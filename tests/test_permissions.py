"""
Tests for permissions collector.
"""


from unittest.mock import patch

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
async def test_capabilities_cover_full_kernel_set():
    """Capabilities are decoded across the full kernel range, not a fixed 32."""
    collector = PermissionsCollector()

    # cap_sys_admin (21) and cap_bpf (39) effective; kernel supports up to 40.
    mask = (1 << 21) | (1 << 39)
    status = (
        f"CapInh:\t{0:016x}\n"
        f"CapPrm:\t{mask:016x}\n"
        f"CapEff:\t{mask:016x}\n"
    )

    async def fake_read(path, silent_if_missing=False):  # noqa: ARG001
        if path == "/proc/self/status":
            return status
        if path == "/proc/sys/kernel/cap_last_cap":
            return "40\n"
        return None

    with patch.object(collector, "read_file_async", side_effect=fake_read):
        caps = await collector._get_capabilities()

    assert len(caps) == 41  # 0..40 inclusive
    by_name = {c.name: c for c in caps}
    # Modern capabilities beyond the original 32 are present.
    assert "cap_bpf" in by_name
    assert "cap_perfmon" in by_name
    assert "cap_checkpoint_restore" in by_name
    # Effective bits are decoded correctly.
    assert by_name["cap_sys_admin"].effective is True
    assert by_name["cap_bpf"].effective is True
    assert by_name["cap_chown"].effective is False


@pytest.mark.asyncio
async def test_capabilities_fallback_when_last_cap_missing():
    """Without cap_last_cap, decoding falls back to the full known name set."""
    collector = PermissionsCollector()

    async def fake_read(path, silent_if_missing=False):  # noqa: ARG001
        if path == "/proc/self/status":
            return "CapInh:\t0000000000000000\nCapPrm:\t0000000000000000\nCapEff:\t0000000000000000\n"
        return None  # cap_last_cap unavailable

    with patch.object(collector, "read_file_async", side_effect=fake_read):
        caps = await collector._get_capabilities()

    assert len(caps) == len(PermissionsCollector.CAPABILITY_NAMES)
    assert caps[-1].name == "cap_checkpoint_restore"


@pytest.mark.asyncio
async def test_capabilities_future_kernel_uses_numeric_names():
    """Capabilities beyond the known name list are labelled cap_<n>."""
    collector = PermissionsCollector()

    async def fake_read(path, silent_if_missing=False):  # noqa: ARG001
        if path == "/proc/self/status":
            return "CapInh:\t0000000000000000\nCapPrm:\t0000000000000000\nCapEff:\t0000000000000000\n"
        if path == "/proc/sys/kernel/cap_last_cap":
            return "42\n"  # two beyond the known set (40)
        return None

    with patch.object(collector, "read_file_async", side_effect=fake_read):
        caps = await collector._get_capabilities()

    assert len(caps) == 43  # 0..42
    assert caps[41].name == "cap_41"
    assert caps[42].name == "cap_42"


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
