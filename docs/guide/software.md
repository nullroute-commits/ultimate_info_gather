# Software Inventory

The software collector catalogs installed software and running processes.

## SoftwareInfo Model

```python
@dataclass
class SoftwareInfo:
    timestamp: datetime
    os_info: OSInfo | None
    kernel_modules: list[KernelModule]
    installed_packages: list[InstalledPackage]
    package_managers_available: list[str]
    python_packages: list[PythonPackage]
    python_version: str
    pip_version: str | None
    virtual_env_active: bool
    virtual_env_path: str | None
    system_services: list[SystemService]
    init_system: str | None
    containers: list[ContainerInfo]
    container_runtimes: list[str]
    running_processes: list[RunningProcess]
    process_count: int
    environment_variables: dict[str, str]
    path_directories: list[str]
    can_install_packages: bool
    can_manage_services: bool
    can_load_modules: bool
    can_manage_containers: bool
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
```

## Operating System Info

| Field | Description |
|-------|-------------|
| `name` | OS name (Ubuntu, Fedora, etc.) |
| `version` | OS version |
| `release` | Kernel release |
| `codename` | Version codename |
| `kernel_version` | Kernel version |
| `architecture` | System architecture |
| `boot_time` | Last boot timestamp |
| `uptime_seconds` | Uptime in seconds |

## Package Managers

Detected package managers:

| Manager | Systems |
|---------|---------|
| `opkg` | OpenWrt, embedded systems (checked first) |
| `apt`, `apt-get`, `dpkg` | Debian/Ubuntu |
| `yum`, `dnf`, `rpm` | RHEL/CentOS/Fedora |
| `pacman` | Arch Linux |
| `zypper` | openSUSE |
| `apk` | Alpine Linux |
| `snap`, `flatpak` | Universal |

## Installed Packages

For each package:

| Field | Description |
|-------|-------------|
| `name` | Package name |
| `version` | Installed version |
| `architecture` | Package architecture |
| `installed_size_bytes` | Disk space used |
| `package_manager` | Source PM |
| `install_date` | When installed |
| `is_automatic` | Installed as dependency |

## Python Packages

Via pip:

| Field | Description |
|-------|-------------|
| `name` | Package name |
| `version` | Installed version |
| `location` | Installation path |
| `requires` | Dependencies |
| `required_by` | Reverse dependencies |
| `is_editable` | Editable install |

## System Services

Systemd services:

| Field | Description |
|-------|-------------|
| `name` | Service name |
| `state` | RUNNING, STOPPED, FAILED, INACTIVE, UNKNOWN |
| `is_enabled` | Starts on boot |
| `pid` | Process ID |
| `user` | Running as user |
| `service_type` | systemd, init, etc. |
| `can_control` | Can start/stop |

## Init Systems

Detected init systems:

- `systemd`
- `upstart`
- `sysvinit`
- `openrc`

## Container Runtimes

Detected runtimes:

- Docker
- Podman
- containerd
- CRI-O
- LXC/LXD

## Running Processes

Top processes:

| Field | Description |
|-------|-------------|
| `pid` | Process ID |
| `name` | Process name |
| `cmdline` | Command line |
| `user` | Running as |
| `status` | Process status |
| `cpu_percent` | CPU usage |
| `memory_percent` | Memory usage |
| `memory_bytes` | Memory in bytes |
| `num_threads` | Thread count |
| `create_time` | Start time |

## Access Capabilities

Boolean flags for what the process can do:

| Capability | Requires |
|------------|----------|
| `can_install_packages` | Root or sudo |
| `can_manage_services` | Root or sudo |
| `can_load_modules` | Root or sudo |
| `can_manage_containers` | docker group or root |

## Usage Example

```python
from src.collectors import SoftwareCollector

async def scan_software():
    collector = SoftwareCollector()
    result = await collector.safe_collect()
    
    if result.success:
        sw = result.data
        
        if sw.os_info:
            print(f"OS: {sw.os_info.name} {sw.os_info.version}")
            print(f"Kernel: {sw.os_info.kernel_version}")
            print(f"Uptime: {sw.os_info.uptime_seconds / 3600:.1f} hours")
        
        print(f"\nPackage Managers: {sw.package_managers_available}")
        print(f"Installed Packages: {len(sw.installed_packages)}")
        print(f"Python Packages: {len(sw.python_packages)}")
        
        print(f"\nInit System: {sw.init_system}")
        print(f"Services: {len(sw.system_services)}")
        
        running = [s for s in sw.system_services if s.state.name == 'RUNNING']
        print(f"Running Services: {len(running)}")
        
        print(f"\nContainer Runtimes: {sw.container_runtimes}")
        print(f"Running Containers: {len(sw.containers)}")
        
        print(f"\nProcess Count: {sw.process_count}")
        
        print("\nCapabilities:")
        print(f"  Can Install Packages: {sw.can_install_packages}")
        print(f"  Can Manage Services: {sw.can_manage_services}")
        print(f"  Can Manage Containers: {sw.can_manage_containers}")
```
