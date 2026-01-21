"""
Software collector - Objective 3 (Part 2).

Collects software information and determines access levels.
"""

from __future__ import annotations

import os
import platform
import re
import sys
from datetime import datetime
from pathlib import Path

from ..models.environment import EnvironmentState
from ..models.permissions import PermissionsInfo
from ..models.software import (
    ContainerInfo,
    InstalledPackage,
    KernelModule,
    OSInfo,
    PythonPackage,
    RunningProcess,
    ServiceState,
    SoftwareInfo,
    SystemService,
)
from .base import BaseCollector


class SoftwareCollector(BaseCollector[SoftwareInfo]):
    """
    Collects comprehensive software information.

    Objective 3: Collect all software deployed and determine access levels.
    """

    def __init__(
        self,
        environment_state: EnvironmentState | None = None,
        permissions_info: PermissionsInfo | None = None,
    ):
        """
        Initialize with optional prior collection results.

        Args:
            environment_state: Previously collected environment info
            permissions_info: Previously collected permissions info
        """
        super().__init__()
        self.env_state = environment_state
        self.perm_info = permissions_info

    async def collect(self) -> SoftwareInfo:
        """Collect software information."""
        timestamp = datetime.now()

        # Collect all software info in parallel where possible
        (
            os_info,
            kernel_modules,
            installed_packages,
            package_managers,
            python_packages,
            system_services,
            init_system,
            containers,
            container_runtimes,
            running_processes,
        ) = await self.gather_with_errors(
            self._get_os_info(),
            self._get_kernel_modules(),
            self._get_installed_packages(),
            self._get_package_managers(),
            self._get_python_packages(),
            self._get_system_services(),
            self._get_init_system(),
            self._get_containers(),
            self._get_container_runtimes(),
            self._get_running_processes(),
        )

        # Get Python info
        python_version = sys.version
        pip_version = await self._get_pip_version()

        # Virtual env info
        virtual_env_active = sys.prefix != sys.base_prefix
        virtual_env_path = sys.prefix if virtual_env_active else None

        # Determine access capabilities
        can_install = await self._check_can_install_packages()
        can_services = await self._check_can_manage_services()
        can_modules = await self._check_can_load_modules()
        can_containers = await self._check_can_manage_containers()

        return SoftwareInfo(
            timestamp=timestamp,
            os_info=os_info,
            kernel_modules=kernel_modules or [],
            installed_packages=installed_packages or [],
            package_managers_available=package_managers or [],
            python_packages=python_packages or [],
            python_version=python_version,
            pip_version=pip_version,
            virtual_env_active=virtual_env_active,
            virtual_env_path=virtual_env_path,
            system_services=system_services or [],
            init_system=init_system,
            containers=containers or [],
            container_runtimes=container_runtimes or [],
            running_processes=running_processes or [],
            process_count=len(running_processes) if running_processes else 0,
            environment_variables=dict(os.environ),
            path_directories=os.environ.get('PATH', '').split(':'),
            can_install_packages=can_install,
            can_manage_services=can_services,
            can_load_modules=can_modules,
            can_manage_containers=can_containers,
            errors=self._errors.copy(),
        )

    async def _get_os_info(self) -> OSInfo | None:
        """Get operating system information."""
        try:
            # Read os-release
            os_release = await self.read_file_async('/etc/os-release')
            name = version = codename = ''

            if os_release:
                for line in os_release.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        value = value.strip('"\'')
                        if key == 'NAME':
                            name = value
                        elif key == 'VERSION':
                            version = value
                        elif key == 'VERSION_CODENAME':
                            codename = value

            # Get kernel info
            uname = platform.uname()

            # Get boot time and uptime
            uptime = 0.0
            boot_time: datetime | None = None
            uptime_content = await self.read_file_async('/proc/uptime')
            if uptime_content:
                uptime = float(uptime_content.split()[0])
                boot_timestamp = datetime.now().timestamp() - uptime
                boot_time = datetime.fromtimestamp(boot_timestamp)

            return OSInfo(
                name=name or uname.system,
                version=version or uname.version,
                release=uname.release,
                codename=codename or None,
                kernel_version=uname.release,
                architecture=uname.machine,
                boot_time=boot_time,
                uptime_seconds=uptime,
            )
        except Exception as e:
            self.add_warning(f"Failed to get OS info: {e}")
            return None

    async def _get_kernel_modules(self) -> list[KernelModule]:
        """Get loaded kernel modules."""
        modules = []

        try:
            modules_content = await self.read_file_async('/proc/modules')
            if modules_content:
                for line in modules_content.strip().split('\n'):
                    parts = line.split()
                    if len(parts) >= 4:
                        name = parts[0]
                        size = int(parts[1])
                        used_by = parts[3].strip(',').split(',') if parts[3] != '-' else []
                        state = parts[4] if len(parts) > 4 else 'Live'

                        modules.append(KernelModule(
                            name=name,
                            size_bytes=size,
                            used_by=[u for u in used_by if u],
                            state=state,
                        ))
        except Exception as e:
            self.add_warning(f"Failed to get kernel modules: {e}")

        return modules

    async def _get_installed_packages(self) -> list[InstalledPackage]:
        """Get installed system packages."""
        packages = []

        # Try opkg (OpenWrt/embedded)
        ret, stdout, _ = await self.run_command(
            ['opkg', 'list-installed'],
            timeout=30,
        )

        if ret == 0 and stdout:
            for line in stdout.strip().split('\n'):
                # Format: package-name - version
                parts = line.split(' - ')
                if len(parts) >= 2:
                    packages.append(InstalledPackage(
                        name=parts[0],
                        version=parts[1],
                        architecture=None,
                        description=None,
                        installed_size_bytes=None,
                        package_manager='opkg',
                        install_date=None,
                        is_automatic=False,
                    ))
            return packages

        # Try dpkg (Debian/Ubuntu)
        ret, stdout, _ = await self.run_command(
            ['dpkg-query', '-W', '-f=${Package}\t${Version}\t${Architecture}\t${Installed-Size}\t${Status}\n'],
            timeout=30,
        )

        if ret == 0 and stdout:
            for line in stdout.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 4 and 'installed' in parts[4].lower() if len(parts) > 4 else True:
                    packages.append(InstalledPackage(
                        name=parts[0],
                        version=parts[1],
                        architecture=parts[2] if len(parts) > 2 else None,
                        description=None,
                        installed_size_bytes=int(parts[3]) * 1024 if parts[3].isdigit() else None,
                        package_manager='dpkg',
                        install_date=None,
                        is_automatic=False,
                    ))
            return packages

        # Try rpm (RHEL/CentOS/Fedora)
        ret, stdout, _ = await self.run_command(
            ['rpm', '-qa', '--queryformat', '%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\t%{SIZE}\n'],
            timeout=30,
        )

        if ret == 0 and stdout:
            for line in stdout.strip().split('\n'):
                parts = line.split('\t')
                if len(parts) >= 4:
                    packages.append(InstalledPackage(
                        name=parts[0],
                        version=parts[1],
                        architecture=parts[2],
                        description=None,
                        installed_size_bytes=int(parts[3]) if parts[3].isdigit() else None,
                        package_manager='rpm',
                        install_date=None,
                        is_automatic=False,
                    ))
            return packages

        # Try pacman (Arch)
        ret, stdout, _ = await self.run_command(
            ['pacman', '-Q'],
            timeout=30,
        )

        if ret == 0 and stdout:
            for line in stdout.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 2:
                    packages.append(InstalledPackage(
                        name=parts[0],
                        version=parts[1],
                        architecture=None,
                        description=None,
                        installed_size_bytes=None,
                        package_manager='pacman',
                        install_date=None,
                        is_automatic=False,
                    ))

        return packages

    async def _get_package_managers(self) -> list[str]:
        """Get available package managers."""
        managers = []

        pm_commands = ['opkg', 'apt', 'apt-get', 'dpkg', 'yum', 'dnf', 'rpm', 'pacman', 'zypper', 'apk', 'snap', 'flatpak']

        for pm in pm_commands:
            ret, _, _ = await self.run_command(['which', pm], timeout=5)
            if ret == 0:
                managers.append(pm)

        return managers

    async def _get_python_packages(self) -> list[PythonPackage]:
        """Get installed Python packages."""
        packages = []

        try:
            # Use pip list
            ret, stdout, _ = await self.run_command(
                [sys.executable, '-m', 'pip', 'list', '--format=json'],
                timeout=30,
            )

            if ret == 0 and stdout:
                import json
                pip_packages = json.loads(stdout)

                for pkg in pip_packages:
                    packages.append(PythonPackage(
                        name=pkg.get('name', ''),
                        version=pkg.get('version', ''),
                        location='',  # Would need pip show for this
                        requires=[],
                        required_by=[],
                        is_editable=False,
                        metadata_version=None,
                    ))
        except Exception as e:
            self.add_warning(f"Failed to get Python packages: {e}")

        return packages

    async def _get_pip_version(self) -> str | None:
        """Get pip version."""
        ret, stdout, _ = await self.run_command(
            [sys.executable, '-m', 'pip', '--version'],
            timeout=10,
        )

        if ret == 0 and stdout:
            # Parse: pip 23.0.1 from /path/to/pip (python 3.11)
            match = re.match(r'pip (\S+)', stdout)
            if match:
                return match.group(1)

        return None

    async def _get_system_services(self) -> list[SystemService]:
        """Get system services."""
        services = []

        # Try systemctl
        ret, stdout, _ = await self.run_command(
            ['systemctl', 'list-units', '--type=service', '--all', '--no-pager', '--plain'],
            timeout=30,
        )

        if ret == 0 and stdout:
            lines = stdout.strip().split('\n')
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    name = parts[0].replace('.service', '')

                    # Determine state
                    state = ServiceState.UNKNOWN
                    if 'running' in line.lower():
                        state = ServiceState.RUNNING
                    elif 'dead' in line.lower() or 'inactive' in line.lower():
                        state = ServiceState.STOPPED
                    elif 'failed' in line.lower():
                        state = ServiceState.FAILED

                    services.append(SystemService(
                        name=name,
                        display_name=None,
                        description=' '.join(parts[4:]) if len(parts) > 4 else None,
                        state=state,
                        is_enabled=False,  # Would need separate query
                        pid=None,
                        user=None,
                        start_time=None,
                        memory_bytes=None,
                        cpu_percent=None,
                        service_type='systemd',
                        can_control=os.geteuid() == 0 if hasattr(os, 'geteuid') else False,
                    ))

        return services

    async def _get_init_system(self) -> str | None:
        """Detect the init system."""
        # Check for systemd
        if Path('/run/systemd/system').exists():
            return 'systemd'

        # Check for upstart
        ret, _, _ = await self.run_command(['initctl', '--version'], timeout=5)
        if ret == 0:
            return 'upstart'

        # Check for sysvinit
        if Path('/etc/init.d').exists():
            return 'sysvinit'

        # Check for openrc
        ret, _, _ = await self.run_command(['rc-status', '--version'], timeout=5)
        if ret == 0:
            return 'openrc'

        return None

    async def _get_containers(self) -> list[ContainerInfo]:
        """Get running containers."""
        containers = []

        # Try Docker
        ret, stdout, _ = await self.run_command(
            ['docker', 'ps', '-a', '--format', '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'],
            timeout=30,
        )

        if ret == 0 and stdout:
            for line in stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 4:
                    containers.append(ContainerInfo(
                        id=parts[0],
                        name=parts[1],
                        image=parts[2],
                        status=parts[3],
                        created=None,
                        ports=[{'port': p} for p in parts[4].split(',') if p] if len(parts) > 4 else [],
                        networks=[],
                        volumes=[],
                        runtime='docker',
                        can_control=True,
                    ))

        # Try Podman
        ret, stdout, _ = await self.run_command(
            ['podman', 'ps', '-a', '--format', '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}'],
            timeout=30,
        )

        if ret == 0 and stdout:
            for line in stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 4:
                    containers.append(ContainerInfo(
                        id=parts[0],
                        name=parts[1],
                        image=parts[2],
                        status=parts[3],
                        created=None,
                        ports=[],
                        networks=[],
                        volumes=[],
                        runtime='podman',
                        can_control=True,
                    ))

        return containers

    async def _get_container_runtimes(self) -> list[str]:
        """Get available container runtimes."""
        runtimes = []

        for runtime in ['docker', 'podman', 'containerd', 'cri-o', 'lxc', 'lxd']:
            ret, _, _ = await self.run_command(['which', runtime], timeout=5)
            if ret == 0:
                runtimes.append(runtime)

        return runtimes

    async def _get_running_processes(self) -> list[RunningProcess]:
        """Get running processes."""
        processes = []

        try:
            proc_path = Path('/proc')
            for entry in proc_path.iterdir():
                if entry.name.isdigit():
                    pid = int(entry.name)

                    try:
                        # Read process info
                        comm = await self.read_file_async(f'/proc/{pid}/comm')
                        cmdline = await self.read_file_async(f'/proc/{pid}/cmdline')
                        status = await self.read_file_async(f'/proc/{pid}/status')

                        if not comm:
                            continue

                        name = comm.strip()
                        cmd_parts = cmdline.replace('\x00', ' ').strip().split() if cmdline else []

                        # Parse status
                        user = 'unknown'
                        proc_status = 'unknown'

                        if status:
                            for line in status.split('\n'):
                                if line.startswith('Uid:'):
                                    uid = int(line.split()[1])
                                    try:
                                        import pwd
                                        user = pwd.getpwuid(uid).pw_name
                                    except Exception:
                                        user = str(uid)
                                elif line.startswith('State:'):
                                    proc_status = line.split()[1]

                        processes.append(RunningProcess(
                            pid=pid,
                            name=name,
                            cmdline=cmd_parts[:10],  # Limit cmdline length
                            user=user,
                            status=proc_status,
                            cpu_percent=0.0,
                            memory_percent=0.0,
                            memory_bytes=0,
                            num_threads=1,
                            create_time=None,
                            cwd=None,
                        ))

                        # Limit to first 100 processes
                        if len(processes) >= 100:
                            break
                    except Exception:
                        continue
        except Exception as e:
            self.add_warning(f"Failed to get processes: {e}")

        return processes

    async def _check_can_install_packages(self) -> bool:
        """Check if we can install packages."""
        # Check for root or sudo
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            return True

        # Check sudo
        ret, _, _ = await self.run_command(['sudo', '-n', 'true'], timeout=5)
        return ret == 0

    async def _check_can_manage_services(self) -> bool:
        """Check if we can manage services."""
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            return True

        ret, _, _ = await self.run_command(['sudo', '-n', 'systemctl', 'list-units'], timeout=5)
        return ret == 0

    async def _check_can_load_modules(self) -> bool:
        """Check if we can load kernel modules."""
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            return True

        ret, _, _ = await self.run_command(['sudo', '-n', 'modprobe', '--dry-run', 'loop'], timeout=5)
        return ret == 0

    async def _check_can_manage_containers(self) -> bool:
        """Check if we can manage containers."""
        # Check Docker socket access
        docker_sock = Path('/var/run/docker.sock')
        if docker_sock.exists() and os.access(str(docker_sock), os.W_OK):
            return True

        # Check if in docker group
        try:
            import grp
            docker_gid = grp.getgrnam('docker').gr_gid
            if docker_gid in os.getgroups():
                return True
        except Exception:
            pass

        # Check podman (rootless)
        ret, _, _ = await self.run_command(['podman', 'info'], timeout=10)
        return ret == 0
