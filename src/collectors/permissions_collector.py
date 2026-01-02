"""
Permissions collector - Objective 2.

Determines permission levels and available resources for the running process.
"""

from __future__ import annotations

import grp
import os
import pwd
import resource
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models.environment import EnvironmentState
from ..models.permissions import (
    CapabilityInfo,
    FileSystemPermission,
    GroupInfo,
    PermissionLevel,
    PermissionsInfo,
    ResourceInfo,
    ResourceLimits,
)
from .base import BaseCollector


class PermissionsCollector(BaseCollector[PermissionsInfo]):
    """
    Collects permission and resource information.
    
    Objective 2: Determine permissions level and resources available.
    """

    # Critical paths to check permissions on
    CRITICAL_PATHS = [
        '/',
        '/etc',
        '/etc/passwd',
        '/etc/shadow',
        '/etc/sudoers',
        '/var/log',
        '/var/run',
        '/tmp',
        '/root',
        '/home',
        '/proc',
        '/sys',
        '/dev',
        '/boot',
        '/usr/bin',
        '/usr/sbin',
    ]

    def __init__(self, environment_state: EnvironmentState | None = None):
        """
        Initialize with optional environment state.
        
        Args:
            environment_state: Previously collected environment info
        """
        super().__init__()
        self.env_state = environment_state

    async def collect(self) -> PermissionsInfo:
        """Collect permissions information."""
        timestamp = datetime.now()

        # Get user info
        user_id, user_name, effective_uid = await self._get_user_info()

        # Get groups
        groups = await self._get_groups()
        privileged_groups = [g.name for g in groups if g.is_privileged]

        # Determine permission level
        permission_level = await self._determine_permission_level(
            user_id, effective_uid, privileged_groups
        )

        # Get Linux capabilities
        capabilities = await self._get_capabilities()
        has_cap_sys_admin = any(c.name == 'cap_sys_admin' and c.effective for c in capabilities)
        has_cap_net_admin = any(c.name == 'cap_net_admin' and c.effective for c in capabilities)
        has_cap_dac_override = any(c.name == 'cap_dac_override' and c.effective for c in capabilities)

        # Check file system permissions
        fs_permissions = await self._check_fs_permissions()

        # Check security contexts
        selinux_enabled, selinux_context = await self._check_selinux()
        apparmor_enabled, apparmor_profile = await self._check_apparmor()

        # Check sudo capabilities
        can_sudo, sudo_nopasswd = await self._check_sudo()

        # Get resource info
        resources = await self._get_resources()

        return PermissionsInfo(
            timestamp=timestamp,
            permission_level=permission_level,
            user_id=user_id,
            user_name=user_name,
            effective_user_id=effective_uid,
            groups=groups,
            privileged_groups=privileged_groups,
            capabilities=capabilities,
            has_cap_sys_admin=has_cap_sys_admin,
            has_cap_net_admin=has_cap_net_admin,
            has_cap_dac_override=has_cap_dac_override,
            fs_permissions=fs_permissions,
            selinux_enabled=selinux_enabled,
            selinux_context=selinux_context,
            apparmor_enabled=apparmor_enabled,
            apparmor_profile=apparmor_profile,
            can_sudo=can_sudo,
            sudo_nopasswd=sudo_nopasswd,
            resources=resources,
            errors=self._errors.copy(),
        )

    async def _get_user_info(self) -> tuple[int | None, str | None, int | None]:
        """Get current user information."""
        try:
            uid = os.getuid() if hasattr(os, 'getuid') else None
            euid = os.geteuid() if hasattr(os, 'geteuid') else None

            user_name = None
            if uid is not None:
                try:
                    user_name = pwd.getpwuid(uid).pw_name
                except KeyError:
                    user_name = os.environ.get('USER', 'unknown')

            return uid, user_name, euid
        except Exception as e:
            self.add_error(f"Failed to get user info: {e}")
            return None, None, None

    async def _get_groups(self) -> list[GroupInfo]:
        """Get user group memberships."""
        groups = []

        try:
            if hasattr(os, 'getgroups'):
                gids = os.getgroups()

                for gid in gids:
                    try:
                        gr = grp.getgrgid(gid)
                        groups.append(GroupInfo.from_gid(gid, gr.gr_name))
                    except KeyError:
                        groups.append(GroupInfo(gid=gid, name=f'gid_{gid}'))
        except Exception as e:
            self.add_warning(f"Failed to get groups: {e}")

        return groups

    async def _determine_permission_level(
        self,
        uid: int | None,
        euid: int | None,
        privileged_groups: list[str],
    ) -> PermissionLevel:
        """Determine the overall permission level."""
        # Root check
        if uid == 0 or euid == 0:
            return PermissionLevel.ROOT

        # Sudo check
        if 'sudo' in privileged_groups or 'wheel' in privileged_groups:
            return PermissionLevel.SUDO

        # Privileged groups check
        if privileged_groups:
            return PermissionLevel.PRIVILEGED

        # Check for sandboxing
        sandbox_content = await self.read_file_async('/proc/self/status')
        if sandbox_content and 'Seccomp:\t2' in sandbox_content:
            return PermissionLevel.SANDBOXED

        # Check if restricted
        if not os.access('/tmp', os.W_OK):
            return PermissionLevel.RESTRICTED

        return PermissionLevel.STANDARD

    async def _get_capabilities(self) -> list[CapabilityInfo]:
        """Get Linux capabilities for the process."""
        capabilities = []

        # Read capability info from /proc/self/status
        status_content = await self.read_file_async('/proc/self/status')
        if not status_content:
            return capabilities

        cap_eff = cap_prm = cap_inh = 0

        for line in status_content.split('\n'):
            if line.startswith('CapEff:'):
                cap_eff = int(line.split(':')[1].strip(), 16)
            elif line.startswith('CapPrm:'):
                cap_prm = int(line.split(':')[1].strip(), 16)
            elif line.startswith('CapInh:'):
                cap_inh = int(line.split(':')[1].strip(), 16)

        # Define known capabilities
        cap_names = [
            'cap_chown', 'cap_dac_override', 'cap_dac_read_search',
            'cap_fowner', 'cap_fsetid', 'cap_kill', 'cap_setgid',
            'cap_setuid', 'cap_setpcap', 'cap_linux_immutable',
            'cap_net_bind_service', 'cap_net_broadcast', 'cap_net_admin',
            'cap_net_raw', 'cap_ipc_lock', 'cap_ipc_owner', 'cap_sys_module',
            'cap_sys_rawio', 'cap_sys_chroot', 'cap_sys_ptrace',
            'cap_sys_pacct', 'cap_sys_admin', 'cap_sys_boot',
            'cap_sys_nice', 'cap_sys_resource', 'cap_sys_time',
            'cap_sys_tty_config', 'cap_mknod', 'cap_lease',
            'cap_audit_write', 'cap_audit_control', 'cap_setfcap',
        ]

        for i, name in enumerate(cap_names):
            if i < 64:  # Standard capabilities
                capabilities.append(CapabilityInfo(
                    name=name,
                    effective=bool(cap_eff & (1 << i)),
                    permitted=bool(cap_prm & (1 << i)),
                    inheritable=bool(cap_inh & (1 << i)),
                ))

        return capabilities

    async def _check_fs_permissions(self) -> dict[str, FileSystemPermission]:
        """Check filesystem permissions on critical paths."""
        permissions = {}

        for path in self.CRITICAL_PATHS:
            perm = await self._check_path_permission(path)
            permissions[path] = perm

        return permissions

    async def _check_path_permission(self, path: str) -> FileSystemPermission:
        """Check permissions for a single path."""
        try:
            p = Path(path)
            exists = p.exists()

            if not exists:
                return FileSystemPermission(
                    path=path,
                    exists=False,
                    readable=False,
                    writable=False,
                    executable=False,
                    is_directory=False,
                )

            readable = os.access(path, os.R_OK)
            writable = os.access(path, os.W_OK)
            executable = os.access(path, os.X_OK)
            is_dir = p.is_dir()

            try:
                st = p.stat()
                owner_uid = st.st_uid
                owner_gid = st.st_gid
                mode = st.st_mode
            except Exception:
                owner_uid = owner_gid = mode = None

            return FileSystemPermission(
                path=path,
                exists=exists,
                readable=readable,
                writable=writable,
                executable=executable,
                is_directory=is_dir,
                owner_uid=owner_uid,
                owner_gid=owner_gid,
                mode=mode,
            )
        except Exception as e:
            self.add_warning(f"Failed to check {path}: {e}")
            return FileSystemPermission(
                path=path,
                exists=False,
                readable=False,
                writable=False,
                executable=False,
                is_directory=False,
            )

    async def _check_selinux(self) -> tuple[bool, str | None]:
        """Check SELinux status and context."""
        # Check if SELinux is enabled
        selinux_path = Path('/sys/fs/selinux')
        if not selinux_path.exists():
            return False, None

        # Get current context
        context = await self.read_file_async('/proc/self/attr/current')
        return True, context.strip() if context else None

    async def _check_apparmor(self) -> tuple[bool, str | None]:
        """Check AppArmor status and profile."""
        # Check if AppArmor is enabled
        apparmor_path = Path('/sys/kernel/security/apparmor')
        if not apparmor_path.exists():
            return False, None

        # Get current profile
        profile = await self.read_file_async('/proc/self/attr/current')
        return True, profile.strip() if profile else None

    async def _check_sudo(self) -> tuple[bool, bool]:
        """Check sudo capabilities."""
        can_sudo = False
        sudo_nopasswd = False

        # Check if sudo is available
        ret, stdout, stderr = await self.run_command(['which', 'sudo'], timeout=5)
        if ret != 0:
            return False, False

        # Check sudo -l (non-destructive)
        ret, stdout, stderr = await self.run_command(
            ['sudo', '-n', '-l'],
            timeout=5,
        )

        if ret == 0:
            can_sudo = True
            sudo_nopasswd = True
        elif 'password' in stderr.lower() or 'password' in stdout.lower():
            can_sudo = True
            sudo_nopasswd = False

        return can_sudo, sudo_nopasswd

    async def _get_resources(self) -> ResourceInfo:
        """Get available system resources."""
        # CPU info
        cpu_count = os.cpu_count() or 1

        # Memory info
        mem_total = mem_avail = 0
        meminfo = await self.read_file_async('/proc/meminfo')
        if meminfo:
            for line in meminfo.split('\n'):
                if line.startswith('MemTotal:'):
                    mem_total = int(line.split()[1]) * 1024
                elif line.startswith('MemAvailable:'):
                    mem_avail = int(line.split()[1]) * 1024

        # Disk partitions
        partitions = await self._get_disk_partitions()

        # Network interfaces
        net_interfaces = await self._get_network_interface_names()

        # Resource limits
        limits = await self._get_resource_limits()

        return ResourceInfo(
            cpu_count=cpu_count,
            cpu_count_logical=cpu_count,
            memory_total_bytes=mem_total,
            memory_available_bytes=mem_avail,
            disk_partitions=partitions,
            network_interfaces=net_interfaces,
            resource_limits=limits,
        )

    async def _get_disk_partitions(self) -> list[dict[str, Any]]:
        """Get disk partition information."""
        partitions = []

        mounts = await self.read_file_async('/proc/mounts')
        if mounts:
            for line in mounts.split('\n'):
                parts = line.split()
                if len(parts) >= 4 and parts[0].startswith('/dev/'):
                    partitions.append({
                        'device': parts[0],
                        'mountpoint': parts[1],
                        'fstype': parts[2],
                        'options': parts[3],
                    })

        return partitions

    async def _get_network_interface_names(self) -> list[str]:
        """Get list of network interface names."""
        interfaces = []

        net_path = Path('/sys/class/net')
        if net_path.exists():
            try:
                interfaces = [d.name for d in net_path.iterdir()]
            except Exception:
                pass

        return interfaces

    async def _get_resource_limits(self) -> ResourceLimits:
        """Get process resource limits."""
        try:
            return ResourceLimits(
                max_open_files=resource.getrlimit(resource.RLIMIT_NOFILE),
                max_processes=resource.getrlimit(resource.RLIMIT_NPROC),
                max_memory=resource.getrlimit(resource.RLIMIT_AS),
                max_stack_size=resource.getrlimit(resource.RLIMIT_STACK),
                max_cpu_time=resource.getrlimit(resource.RLIMIT_CPU),
                max_file_size=resource.getrlimit(resource.RLIMIT_FSIZE),
                max_core_size=resource.getrlimit(resource.RLIMIT_CORE),
            )
        except Exception as e:
            self.add_warning(f"Failed to get resource limits: {e}")
            return ResourceLimits()
