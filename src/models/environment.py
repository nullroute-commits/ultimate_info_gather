"""
Environment state data model.

Captures the current execution environment and running state of the script.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any


class ExecutionMode(Enum):
    """Execution mode of the script."""
    INTERACTIVE = auto()
    SCRIPT = auto()
    MODULE = auto()
    SUBPROCESS = auto()
    CONTAINER = auto()
    VIRTUAL_ENV = auto()
    UNKNOWN = auto()


class PlatformType(Enum):
    """Platform type classification."""
    LINUX = auto()
    WINDOWS = auto()
    MACOS = auto()
    BSD = auto()
    UNKNOWN = auto()


@dataclass
class PythonEnvironment:
    """Python runtime environment details."""
    version: str
    version_info: tuple[int, int, int, str, int]
    implementation: str
    executable: str
    prefix: str
    base_prefix: str
    is_virtual_env: bool
    platform: str
    path: list[str]

    @classmethod
    def capture(cls) -> PythonEnvironment:
        """Capture current Python environment."""
        return cls(
            version=sys.version,
            version_info=tuple(sys.version_info),
            implementation=sys.implementation.name,
            executable=sys.executable,
            prefix=sys.prefix,
            base_prefix=sys.base_prefix,
            is_virtual_env=sys.prefix != sys.base_prefix,
            platform=sys.platform,
            path=sys.path.copy(),
        )


@dataclass
class ProcessInfo:
    """Current process information."""
    pid: int
    ppid: int
    uid: int | None
    gid: int | None
    euid: int | None
    egid: int | None
    cwd: str
    argv: list[str]

    @classmethod
    def capture(cls) -> ProcessInfo:
        """Capture current process info."""
        uid = gid = euid = egid = None
        if hasattr(os, 'getuid'):
            uid = os.getuid()
            gid = os.getgid()
            euid = os.geteuid()
            egid = os.getegid()

        return cls(
            pid=os.getpid(),
            ppid=os.getppid(),
            uid=uid,
            gid=gid,
            euid=euid,
            egid=egid,
            cwd=os.getcwd(),
            argv=sys.argv.copy(),
        )


@dataclass
class EnvironmentState:
    """
    Complete environment state capturing.
    
    Stores comprehensive information about the execution environment
    including Python runtime, process details, and system variables.
    """
    timestamp: datetime
    python_env: PythonEnvironment
    process_info: ProcessInfo
    execution_mode: ExecutionMode
    platform_type: PlatformType
    environment_variables: dict[str, str]
    hostname: str
    is_root: bool
    is_container: bool
    is_wsl: bool
    terminal_type: str | None
    shell: str | None
    home_directory: str
    temp_directory: str

    # Metadata
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "python_env": {
                "version": self.python_env.version,
                "version_info": list(self.python_env.version_info),
                "implementation": self.python_env.implementation,
                "executable": self.python_env.executable,
                "prefix": self.python_env.prefix,
                "base_prefix": self.python_env.base_prefix,
                "is_virtual_env": self.python_env.is_virtual_env,
                "platform": self.python_env.platform,
                "path": self.python_env.path,
            },
            "process_info": {
                "pid": self.process_info.pid,
                "ppid": self.process_info.ppid,
                "uid": self.process_info.uid,
                "gid": self.process_info.gid,
                "euid": self.process_info.euid,
                "egid": self.process_info.egid,
                "cwd": self.process_info.cwd,
                "argv": self.process_info.argv,
            },
            "execution_mode": self.execution_mode.name,
            "platform_type": self.platform_type.name,
            "hostname": self.hostname,
            "is_root": self.is_root,
            "is_container": self.is_container,
            "is_wsl": self.is_wsl,
            "terminal_type": self.terminal_type,
            "shell": self.shell,
            "home_directory": self.home_directory,
            "temp_directory": self.temp_directory,
            "collection_duration_ms": self.collection_duration_ms,
            "errors": self.errors,
        }

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            "=" * 60,
            "ENVIRONMENT STATE SUMMARY",
            "=" * 60,
            f"Timestamp: {self.timestamp.isoformat()}",
            f"Platform: {self.platform_type.name}",
            f"Hostname: {self.hostname}",
            f"Execution Mode: {self.execution_mode.name}",
            "",
            "Python Environment:",
            f"  Version: {self.python_env.version.split()[0]}",
            f"  Implementation: {self.python_env.implementation}",
            f"  Virtual Env: {self.python_env.is_virtual_env}",
            f"  Executable: {self.python_env.executable}",
            "",
            "Process Info:",
            f"  PID: {self.process_info.pid}",
            f"  PPID: {self.process_info.ppid}",
            f"  UID/GID: {self.process_info.uid}/{self.process_info.gid}",
            f"  CWD: {self.process_info.cwd}",
            "",
            "Environment:",
            f"  Is Root: {self.is_root}",
            f"  Is Container: {self.is_container}",
            f"  Is WSL: {self.is_wsl}",
            f"  Shell: {self.shell}",
            f"  Terminal: {self.terminal_type}",
            "=" * 60,
        ]
        return "\n".join(lines)
