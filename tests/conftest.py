"""
Test fixtures and configuration for pytest.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock


@pytest.fixture
def mock_cpuinfo():
    """Sample /proc/cpuinfo content."""
    return """processor       : 0
vendor_id       : GenuineIntel
model name      : Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz
flags           : fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush dts acpi mmx fxsr sse sse2 ss ht tm pbe syscall nx pdpe1gb rdtscp lm constant_tsc art arch_perfmon pebs bts rep_good nopl xtopology nonstop_tsc cpuid aperfmperf tsc_known_freq pni pclmulqdq dtes64 monitor ds_cpl vmx smx est tm2 ssse3 sdbg fma cx16 xtpr pdcm pcid sse4_1 sse4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand lahf_lm abm 3dnowprefetch cpuid_fault epb invpcid_single ssbd ibrs ibpb stibp tpr_shadow vnmi flexpriority ept vpid ept_ad fsgsbase tsc_adjust bmi1 avx2 smep bmi2 erms invpcid mpx rdseed adx smap clflushopt intel_pt xsaveopt xsavec xgetbv1 xsaves dtherm ida arat pln pts hwp hwp_notify hwp_act_window hwp_epp md_clear flush_l1d arch_capabilities
physical id     : 0
cache size      : 12288 KB
"""


@pytest.fixture
def mock_meminfo():
    """Sample /proc/meminfo content."""
    return """MemTotal:       16384000 kB
MemFree:         4096000 kB
MemAvailable:    8192000 kB
Buffers:          512000 kB
Cached:          2048000 kB
SwapTotal:       4096000 kB
SwapFree:        4096000 kB
"""


@pytest.fixture
def mock_os_release():
    """Sample /etc/os-release content."""
    return """NAME="Ubuntu"
VERSION="22.04.3 LTS (Jammy Jellyfish)"
ID=ubuntu
ID_LIKE=debian
VERSION_ID="22.04"
VERSION_CODENAME=jammy
"""


@pytest.fixture
def mock_environment_state():
    """Create a mock environment state."""
    from src.models.environment import (
        EnvironmentState,
        ExecutionMode,
        PlatformType,
        ProcessInfo,
        PythonEnvironment,
    )
    
    return EnvironmentState(
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
        environment_variables={"HOME": "/home/user", "PATH": "/usr/bin"},
        hostname="testhost",
        is_root=False,
        is_container=False,
        is_wsl=False,
        terminal_type="xterm-256color",
        shell="/bin/bash",
        home_directory="/home/user",
        temp_directory="/tmp",
    )


@pytest.fixture
def async_mock():
    """Create an AsyncMock for patching async methods."""
    return AsyncMock
