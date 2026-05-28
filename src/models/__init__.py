"""
Data models for system information collection.
"""

from .environment import EnvironmentState
from .hardware import HardwareInfo
from .network import NetworkInfo
from .permissions import PermissionsInfo, ResourceInfo
from .proxmox import ProxmoxInfo
from .report import SystemReport
from .software import SoftwareInfo

__all__ = [
    "EnvironmentState",
    "PermissionsInfo",
    "ResourceInfo",
    "HardwareInfo",
    "NetworkInfo",
    "ProxmoxInfo",
    "SoftwareInfo",
    "SystemReport",
]
