"""
Ultimate Info Gather - Async System Information Collection Framework
====================================================================

A comprehensive async Python 3.11+ OOP framework for collecting system
environment, permissions, hardware, and software information.
"""

__version__ = "1.0.0"
__author__ = "System Administrator"

from .models import (
    EnvironmentState,
    PermissionsInfo,
    ResourceInfo,
    HardwareInfo,
    SoftwareInfo,
    SystemReport,
)
from .collectors import (
    EnvironmentCollector,
    PermissionsCollector,
    HardwareCollector,
    SoftwareCollector,
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
