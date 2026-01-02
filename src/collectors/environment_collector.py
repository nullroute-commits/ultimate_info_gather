"""
Environment collector - Objective 1.

Collects current environment and determines running state of the script.
"""

from __future__ import annotations

import os
import platform
import socket
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from ..models.environment import (
    EnvironmentState,
    ExecutionMode,
    PlatformType,
    ProcessInfo,
    PythonEnvironment,
)
from .base import BaseCollector


class EnvironmentCollector(BaseCollector[EnvironmentState]):
    """
    Collects comprehensive environment information.
    
    Objective 1: Collect current env and determine running state.
    """

    async def collect(self) -> EnvironmentState:
        """Collect environment state information."""
        timestamp = datetime.now()

        # Capture Python and process info synchronously (fast operations)
        python_env = PythonEnvironment.capture()
        process_info = ProcessInfo.capture()

        # Determine execution mode
        execution_mode = await self._determine_execution_mode()

        # Determine platform type
        platform_type = self._determine_platform_type()

        # Collect environment variables
        env_vars = dict(os.environ)

        # Get hostname
        hostname = await self._get_hostname()

        # Determine various states
        is_root = await self._check_is_root()
        is_container = await self._check_is_container()
        is_wsl = await self._check_is_wsl()

        # Get terminal info
        terminal_type = os.environ.get('TERM')
        shell = os.environ.get('SHELL')

        # Get directories
        home_dir = str(Path.home())
        temp_dir = tempfile.gettempdir()

        return EnvironmentState(
            timestamp=timestamp,
            python_env=python_env,
            process_info=process_info,
            execution_mode=execution_mode,
            platform_type=platform_type,
            environment_variables=env_vars,
            hostname=hostname,
            is_root=is_root,
            is_container=is_container,
            is_wsl=is_wsl,
            terminal_type=terminal_type,
            shell=shell,
            home_directory=home_dir,
            temp_directory=temp_dir,
            errors=self._errors.copy(),
        )

    async def _determine_execution_mode(self) -> ExecutionMode:
        """Determine how the script is being executed."""
        # Check if in virtual environment
        if sys.prefix != sys.base_prefix:
            return ExecutionMode.VIRTUAL_ENV

        # Check if in container
        if await self._check_is_container():
            return ExecutionMode.CONTAINER

        # Check if running as module (-m)
        if hasattr(sys, '_xoptions') or '__main__' in sys.modules:
            main_spec = getattr(sys.modules.get('__main__'), '__spec__', None)
            if main_spec is not None:
                return ExecutionMode.MODULE

        # Check if interactive
        if hasattr(sys, 'ps1') or sys.flags.interactive:
            return ExecutionMode.INTERACTIVE

        # Check if subprocess
        ppid = os.getppid()
        if ppid > 1:
            parent_name = await self._get_process_name(ppid)
            if parent_name and 'python' in parent_name.lower():
                return ExecutionMode.SUBPROCESS

        # Default to script
        return ExecutionMode.SCRIPT

    def _determine_platform_type(self) -> PlatformType:
        """Determine the platform type."""
        system = platform.system().lower()

        if system == 'linux':
            return PlatformType.LINUX
        elif system == 'windows':
            return PlatformType.WINDOWS
        elif system == 'darwin':
            return PlatformType.MACOS
        elif 'bsd' in system:
            return PlatformType.BSD
        else:
            return PlatformType.UNKNOWN

    async def _get_hostname(self) -> str:
        """Get the system hostname."""
        try:
            return socket.gethostname()
        except Exception as e:
            self.add_warning(f"Failed to get hostname: {e}")
            return "unknown"

    async def _check_is_root(self) -> bool:
        """Check if running as root."""
        if hasattr(os, 'geteuid'):
            return os.geteuid() == 0
        return False

    async def _check_is_container(self) -> bool:
        """Check if running inside a container."""
        # Check for Docker
        if Path('/.dockerenv').exists():
            return True

        # Check cgroup for container markers
        cgroup_content = await self.read_file_async('/proc/1/cgroup')
        if cgroup_content:
            markers = ['docker', 'kubepods', 'lxc', 'containerd']
            if any(marker in cgroup_content.lower() for marker in markers):
                return True

        # Check for container environment variables
        container_env_vars = ['KUBERNETES_SERVICE_HOST', 'DOCKER_CONTAINER']
        if any(var in os.environ for var in container_env_vars):
            return True

        return False

    async def _check_is_wsl(self) -> bool:
        """Check if running under Windows Subsystem for Linux."""
        # Check kernel release
        try:
            uname = platform.uname()
            if 'microsoft' in uname.release.lower() or 'wsl' in uname.release.lower():
                return True
        except Exception:
            pass

        # Check /proc/version
        version_content = await self.read_file_async('/proc/version')
        if version_content and 'microsoft' in version_content.lower():
            return True

        return False

    async def _get_process_name(self, pid: int) -> str | None:
        """Get process name by PID."""
        cmdline_content = await self.read_file_async(f'/proc/{pid}/comm')
        if cmdline_content:
            return cmdline_content.strip()
        return None
