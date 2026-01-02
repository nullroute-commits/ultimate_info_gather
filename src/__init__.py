"""
Ultimate Info Gather - Async System Information Collection Framework
====================================================================

A comprehensive async Python 3.11+ OOP framework for collecting system
environment, permissions, hardware, and software information.
"""

__version__ = "1.0.0"
__author__ = "System Administrator"

from .collectors import (
    EnvironmentCollector,
    HardwareCollector,
    PermissionsCollector,
    SoftwareCollector,
)
from .models import (
    EnvironmentState,
    HardwareInfo,
    PermissionsInfo,
    ResourceInfo,
    SoftwareInfo,
    SystemReport,
)
from .orchestrator import InfoGatherOrchestrator

__all__ = [
    "EnvironmentState",
    "PermissionsInfo",
    "ResourceInfo",
    "HardwareInfo",
    "SoftwareInfo",
    "SystemReport",
    "EnvironmentCollector",
    "PermissionsCollector",
    "HardwareCollector",
    "SoftwareCollector",
    "InfoGatherOrchestrator",
]
