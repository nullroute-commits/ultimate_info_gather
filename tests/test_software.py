"""
Tests for the software collector, focused on complete datapoint collection.

Covers per-process telemetry (BUG-03) and systemd service enrichment (BUG-04).
"""

from datetime import datetime
from unittest.mock import patch

import pytest

from src.collectors.software_collector import SoftwareCollector
from src.models.software import ServiceState

# ---------------------------------------------------------------------------
# /proc/<pid>/stat parsing
# ---------------------------------------------------------------------------

def test_parse_proc_stat_basic():
    """Resource fields are extracted from a standard stat line."""
    stat = "12345 (myproc) S 1 12345 12345 0 -1 4194560 100 0 0 0 100 200 0 0 20 0 4 0 50000 0 0"
    parsed = SoftwareCollector._parse_proc_stat(stat)

    assert parsed == (100, 200, 4, 50000)


def test_parse_proc_stat_comm_with_spaces_and_parens():
    """comm containing spaces and parentheses does not break field parsing."""
    stat = "1234 ((weird) name) S 1 1234 1234 0 -1 0 10 20 0 0 111 222 0 0 20 0 7 0 999 0 0"
    parsed = SoftwareCollector._parse_proc_stat(stat)

    # utime, stime, num_threads, starttime taken after the final ')'
    assert parsed == (111, 222, 7, 999)


def test_parse_proc_stat_malformed_returns_none():
    """Malformed content yields None instead of raising."""
    assert SoftwareCollector._parse_proc_stat("not a real stat line") is None
    assert SoftwareCollector._parse_proc_stat("") is None


def test_resolve_username_caches():
    """Username resolution caches results per uid."""
    cache: dict[int, str] = {}
    name = SoftwareCollector._resolve_username(0, cache)

    assert name == cache[0]
    # Unknown uid falls back to the numeric id as a string.
    assert SoftwareCollector._resolve_username(999999, cache) == "999999"


@pytest.mark.asyncio
async def test_running_process_telemetry_populated():
    """A captured process reports real CPU, memory, threads, start time, cwd."""
    collector = SoftwareCollector()

    status = (
        "Name:\tmyproc\n"
        "Uid:\t0\t0\t0\t0\n"
        "State:\tS (sleeping)\n"
        "VmRSS:\t2048 kB\n"
        "Threads:\t4\n"
    )
    stat = "12345 (myproc) S 1 12345 12345 0 -1 4194560 100 0 0 0 100 200 0 0 20 0 4 0 50000 0 0"

    async def fake_read(path, silent_if_missing=False):  # noqa: ARG001
        if path.endswith("/comm"):
            return "myproc\n"
        if path.endswith("/cmdline"):
            return "python\x00main.py\x00"
        if path.endswith("/status"):
            return status
        if path.endswith("/stat"):
            return stat
        return None

    ctx = {
        "clk_tck": 100.0,
        "uptime_seconds": 1000.0,
        "boot_time_epoch": 1_000_000.0,
        "mem_total_bytes": 1_000_000_000.0,
    }

    from pathlib import Path
    with patch.object(collector, "_get_process_context", return_value=ctx), \
         patch.object(collector, "read_file_async", side_effect=fake_read), \
         patch("pathlib.Path.iterdir", return_value=iter([Path("/proc/12345")])), \
         patch("os.readlink", return_value="/home/test"):
        procs = await collector._get_running_processes()

    assert len(procs) == 1
    p = procs[0]
    assert p.pid == 12345
    assert p.name == "myproc"
    assert p.user == "root"  # uid 0
    assert p.num_threads == 4
    assert p.memory_bytes == 2048 * 1024
    # cpu%: total=(100+200)/100=3s over uptime 1000-500=500s -> 0.6%
    assert p.cpu_percent == 0.6
    # mem%: 2097152 / 1e9 * 100 -> 0.21
    assert p.memory_percent == 0.21
    assert p.create_time == datetime.fromtimestamp(1_000_000 + 50000 / 100)
    assert p.cwd == "/home/test"


@pytest.mark.asyncio
async def test_running_processes_real_system_are_complete():
    """On a real /proc, at least one process exposes non-placeholder telemetry."""
    collector = SoftwareCollector()
    procs = await collector._get_running_processes()

    assert procs, "expected at least one process on a real system"
    # Types are always correct.
    for p in procs:
        assert isinstance(p.cpu_percent, float)
        assert isinstance(p.memory_percent, float)
        assert isinstance(p.memory_bytes, int)
        assert p.memory_bytes >= 0
        assert p.num_threads >= 1

    # At least one userspace process should have real resident memory and a
    # start time, proving the fields are no longer hardcoded placeholders.
    assert any(p.memory_bytes > 0 for p in procs)
    assert any(p.create_time is not None for p in procs)


# ---------------------------------------------------------------------------
# systemctl show parsing / service enrichment
# ---------------------------------------------------------------------------

SHOW_OUTPUT = """Id=cron.service
Description=Regular background program processing daemon
LoadState=loaded
ActiveState=active
SubState=running
UnitFileState=enabled
MainPID=1014
User=
ExecMainStartTimestamp=Sat 2026-08-15 03:07:57 UTC
MemoryCurrent=720896
CPUUsageNSec=27685000

Id=ssh.service
Description=OpenBSD Secure Shell server
LoadState=loaded
ActiveState=inactive
SubState=dead
UnitFileState=disabled
MainPID=0
User=
ExecMainStartTimestamp=
MemoryCurrent=[not set]
CPUUsageNSec=[not set]
"""

LIST_UNITS_OUTPUT = """UNIT LOAD ACTIVE SUB DESCRIPTION
cron.service loaded active running Regular background program processing daemon
ssh.service loaded inactive dead OpenBSD Secure Shell server
"""


def test_parse_systemctl_show_blocks():
    """Blocks separated by blank lines are keyed by unit Id."""
    parsed = SoftwareCollector._parse_systemctl_show(SHOW_OUTPUT)

    assert set(parsed) == {"cron.service", "ssh.service"}
    assert parsed["cron.service"]["MainPID"] == "1014"
    assert parsed["ssh.service"]["MemoryCurrent"] == "[not set]"


def test_map_service_state():
    """Active/sub states map to the ServiceState enum."""
    assert SoftwareCollector._map_service_state("active", "running") == ServiceState.RUNNING
    assert SoftwareCollector._map_service_state("failed", "failed") == ServiceState.FAILED
    assert SoftwareCollector._map_service_state("inactive", "dead") == ServiceState.STOPPED
    assert SoftwareCollector._map_service_state("active", "exited") == ServiceState.RUNNING
    assert SoftwareCollector._map_service_state("reloading", "") == ServiceState.UNKNOWN


def test_parse_systemd_timestamp():
    """A systemd timestamp parses to a naive datetime; empties return None."""
    ts = SoftwareCollector._parse_systemd_timestamp("Sat 2026-08-15 03:07:57 UTC")
    assert ts == datetime(2026, 8, 15, 3, 7, 57)
    assert SoftwareCollector._parse_systemd_timestamp("") is None
    assert SoftwareCollector._parse_systemd_timestamp("n/a") is None


def test_parse_systemd_counter():
    """Numeric counters parse; sentinels and non-numbers return None."""
    assert SoftwareCollector._parse_systemd_counter("720896") == 720896
    assert SoftwareCollector._parse_systemd_counter("[not set]") is None
    assert SoftwareCollector._parse_systemd_counter("") is None
    # UINT64_MAX sentinel means "not available".
    assert SoftwareCollector._parse_systemd_counter(str(2**64 - 1)) is None


def test_build_service_from_show_active():
    """An active unit is fully populated from show properties."""
    collector = SoftwareCollector()
    props = SoftwareCollector._parse_systemctl_show(SHOW_OUTPUT)["cron.service"]

    svc = collector._build_service_from_show(props, can_control=True)

    assert svc.name == "cron"
    assert svc.state == ServiceState.RUNNING
    assert svc.is_enabled is True
    assert svc.pid == 1014
    assert svc.user is None  # empty User= means default (root)
    assert svc.start_time == datetime(2026, 8, 15, 3, 7, 57)
    assert svc.memory_bytes == 720896
    assert svc.cpu_percent is not None and svc.cpu_percent >= 0.0
    assert svc.can_control is True


def test_build_service_from_show_inactive():
    """An inactive unit leaves runtime fields unset but enabled/state correct."""
    collector = SoftwareCollector()
    props = SoftwareCollector._parse_systemctl_show(SHOW_OUTPUT)["ssh.service"]

    svc = collector._build_service_from_show(props, can_control=False)

    assert svc.name == "ssh"
    assert svc.state == ServiceState.STOPPED
    assert svc.is_enabled is False
    assert svc.pid is None
    assert svc.start_time is None
    assert svc.memory_bytes is None
    assert svc.cpu_percent is None


@pytest.mark.asyncio
async def test_get_system_services_enriches_units():
    """list-units discovery is enriched by a batched systemctl show call."""
    collector = SoftwareCollector()

    async def mock_run(cmd, timeout=30):  # noqa: ARG001
        if cmd[:2] == ["systemctl", "list-units"]:
            return (0, LIST_UNITS_OUTPUT, "")
        if cmd[:2] == ["systemctl", "show"]:
            return (0, SHOW_OUTPUT, "")
        return (-1, "", "not found")

    with patch.object(collector, "run_command", side_effect=mock_run):
        services = await collector._get_system_services()

    by_name = {s.name: s for s in services}
    assert set(by_name) == {"cron", "ssh"}
    assert by_name["cron"].is_enabled is True
    assert by_name["cron"].pid == 1014
    assert by_name["cron"].memory_bytes == 720896
    assert by_name["ssh"].is_enabled is False
    assert by_name["ssh"].pid is None


@pytest.mark.asyncio
async def test_get_system_services_no_systemctl():
    """When systemctl is unavailable, service discovery degrades gracefully."""
    collector = SoftwareCollector()

    async def mock_run(cmd, timeout=30):  # noqa: ARG001
        return (-1, "", "command not found")

    with patch.object(collector, "run_command", side_effect=mock_run):
        services = await collector._get_system_services()

    assert services == []
