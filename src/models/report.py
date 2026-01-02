"""
System report data model.

Aggregates all collected information into a comprehensive report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .environment import EnvironmentState
from .hardware import HardwareInfo
from .permissions import PermissionsInfo
from .software import SoftwareInfo


@dataclass
class SystemReport:
    """
    Complete system information report.
    
    Aggregates all collected information from environment, permissions,
    hardware, and software collectors into a unified report.
    """

    # Report metadata
    report_id: str
    generated_at: datetime
    generator_version: str

    # Collected information
    environment: EnvironmentState | None = None
    permissions: PermissionsInfo | None = None
    hardware: HardwareInfo | None = None
    software: SoftwareInfo | None = None

    # Collection metadata
    total_collection_time_ms: float = 0.0
    collection_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert entire report to dictionary."""
        return {
            "report_metadata": {
                "report_id": self.report_id,
                "generated_at": self.generated_at.isoformat(),
                "generator_version": self.generator_version,
                "total_collection_time_ms": self.total_collection_time_ms,
                "collection_errors": self.collection_errors,
                "warnings": self.warnings,
            },
            "environment": self.environment.to_dict() if self.environment else None,
            "permissions": self.permissions.to_dict() if self.permissions else None,
            "hardware": self.hardware.to_dict() if self.hardware else None,
            "software": self.software.to_dict() if self.software else None,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save_json(self, path: Path | str) -> None:
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json())

    def get_full_summary(self) -> str:
        """Get complete human-readable summary."""
        lines = [
            "#" * 70,
            "#" + " " * 20 + "SYSTEM INFORMATION REPORT" + " " * 21 + "#",
            "#" * 70,
            "",
            f"Report ID: {self.report_id}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Generator Version: {self.generator_version}",
            f"Total Collection Time: {self.total_collection_time_ms:.2f} ms",
            "",
        ]

        if self.collection_errors:
            lines.append(f"Errors ({len(self.collection_errors)}):")
            for error in self.collection_errors:
                lines.append(f"  - {error}")
            lines.append("")

        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  - {warning}")
            lines.append("")

        if self.environment:
            lines.append(self.environment.get_summary())
            lines.append("")

        if self.permissions:
            lines.append(self.permissions.get_summary())
            lines.append("")

        if self.hardware:
            lines.append(self.hardware.get_summary())
            lines.append("")

        if self.software:
            lines.append(self.software.get_summary())
            lines.append("")

        lines.extend([
            "#" * 70,
            "#" + " " * 22 + "END OF REPORT" + " " * 22 + "#",
            "#" * 70,
        ])

        return "\n".join(lines)

    def get_markdown_report(self) -> str:
        """Generate a Markdown-formatted report."""
        lines = [
            "# System Information Report",
            "",
            f"**Report ID:** `{self.report_id}`  ",
            f"**Generated:** {self.generated_at.isoformat()}  ",
            f"**Version:** {self.generator_version}  ",
            f"**Collection Time:** {self.total_collection_time_ms:.2f} ms",
            "",
        ]

        if self.collection_errors:
            lines.extend([
                "## ⚠️ Errors",
                "",
            ])
            for error in self.collection_errors:
                lines.append(f"- {error}")
            lines.append("")

        # Environment section
        if self.environment:
            env = self.environment
            lines.extend([
                "## 🖥️ Environment",
                "",
                "### Python Environment",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| Version | {env.python_env.version.split()[0]} |",
                f"| Implementation | {env.python_env.implementation} |",
                f"| Virtual Env | {env.python_env.is_virtual_env} |",
                f"| Executable | `{env.python_env.executable}` |",
                "",
                "### Process Info",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| PID | {env.process_info.pid} |",
                f"| PPID | {env.process_info.ppid} |",
                f"| UID/GID | {env.process_info.uid}/{env.process_info.gid} |",
                f"| CWD | `{env.process_info.cwd}` |",
                "",
                "### System",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| Hostname | {env.hostname} |",
                f"| Platform | {env.platform_type.name} |",
                f"| Is Root | {env.is_root} |",
                f"| Is Container | {env.is_container} |",
                f"| Is WSL | {env.is_wsl} |",
                "",
            ])

        # Permissions section
        if self.permissions:
            perm = self.permissions
            lines.extend([
                "## 🔐 Permissions",
                "",
                f"**Permission Level:** `{perm.permission_level.name}`",
                "",
                "### User Info",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| Username | {perm.user_name} |",
                f"| UID | {perm.user_id} |",
                f"| Effective UID | {perm.effective_user_id} |",
                f"| Groups | {len(perm.groups)} |",
                f"| Privileged Groups | {', '.join(perm.privileged_groups) or 'None'} |",
                "",
                "### Capabilities",
                "",
                "| Capability | Status |",
                "|------------|--------|",
                f"| CAP_SYS_ADMIN | {'✅' if perm.has_cap_sys_admin else '❌'} |",
                f"| CAP_NET_ADMIN | {'✅' if perm.has_cap_net_admin else '❌'} |",
                f"| CAP_DAC_OVERRIDE | {'✅' if perm.has_cap_dac_override else '❌'} |",
                "",
                "### Security Context",
                "",
                "| Feature | Status |",
                "|---------|--------|",
                f"| SELinux | {'Enabled' if perm.selinux_enabled else 'Disabled'} |",
                f"| AppArmor | {'Enabled' if perm.apparmor_enabled else 'Disabled'} |",
                f"| Can Sudo | {'✅' if perm.can_sudo else '❌'} |",
                "",
            ])

        # Hardware section
        if self.hardware:
            hw = self.hardware
            lines.extend([
                "## 🔧 Hardware",
                "",
            ])

            if hw.cpu:
                lines.extend([
                    "### CPU",
                    "",
                    "| Property | Value |",
                    "|----------|-------|",
                    f"| Model | {hw.cpu.model_name} |",
                    f"| Architecture | {hw.cpu.architecture} |",
                    f"| Physical Cores | {hw.cpu.physical_cores} |",
                    f"| Logical Cores | {hw.cpu.logical_cores} |",
                    f"| Virtualization | {hw.cpu.virtualization_supported} |",
                    "",
                ])

            if hw.memory:
                total_gb = hw.memory.total_bytes / (1024**3)
                avail_gb = hw.memory.available_bytes / (1024**3)
                lines.extend([
                    "### Memory",
                    "",
                    "| Property | Value |",
                    "|----------|-------|",
                    f"| Total | {total_gb:.2f} GB |",
                    f"| Available | {avail_gb:.2f} GB |",
                    f"| Used | {hw.memory.percent_used:.1f}% |",
                    "",
                ])

            lines.extend([
                "### Summary",
                "",
                "| Component | Count |",
                "|-----------|-------|",
                f"| Storage Devices | {len(hw.storage_devices)} |",
                f"| Network Interfaces | {len(hw.network_interfaces)} |",
                f"| GPUs | {len(hw.gpus)} |",
                f"| USB Devices | {len(hw.usb_devices)} |",
                "",
                f"**Virtual Machine:** {hw.is_virtual_machine}",
            ])

            if hw.is_virtual_machine and hw.hypervisor:
                lines.append(f"  \n**Hypervisor:** {hw.hypervisor}")
            lines.append("")

        # Software section
        if self.software:
            sw = self.software
            lines.extend([
                "## 📦 Software",
                "",
            ])

            if sw.os_info:
                lines.extend([
                    "### Operating System",
                    "",
                    "| Property | Value |",
                    "|----------|-------|",
                    f"| Name | {sw.os_info.name} |",
                    f"| Version | {sw.os_info.version} |",
                    f"| Kernel | {sw.os_info.kernel_version} |",
                    f"| Architecture | {sw.os_info.architecture} |",
                    f"| Uptime | {sw.os_info.uptime_seconds / 3600:.1f} hours |",
                    "",
                ])

            lines.extend([
                "### Package Management",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| Package Managers | {', '.join(sw.package_managers_available) or 'None'} |",
                f"| Installed Packages | {len(sw.installed_packages)} |",
                f"| Python Packages | {len(sw.python_packages)} |",
                f"| Can Install | {'✅' if sw.can_install_packages else '❌'} |",
                "",
                "### Services & Processes",
                "",
                "| Property | Value |",
                "|----------|-------|",
                f"| Init System | {sw.init_system} |",
                f"| Services | {len(sw.system_services)} |",
                f"| Processes | {sw.process_count} |",
                f"| Container Runtimes | {', '.join(sw.container_runtimes) or 'None'} |",
                f"| Running Containers | {len(sw.containers)} |",
                "",
                "### Access Summary",
                "",
                "| Capability | Status |",
                "|------------|--------|",
                f"| Install Packages | {'✅' if sw.can_install_packages else '❌'} |",
                f"| Manage Services | {'✅' if sw.can_manage_services else '❌'} |",
                f"| Load Kernel Modules | {'✅' if sw.can_load_modules else '❌'} |",
                f"| Manage Containers | {'✅' if sw.can_manage_containers else '❌'} |",
                "",
            ])

        lines.extend([
            "---",
            "",
            f"*Report generated by Ultimate Info Gather v{self.generator_version}*",
        ])

        return "\n".join(lines)

    def save_markdown(self, path: Path | str) -> None:
        """Save report as Markdown file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.get_markdown_report())
