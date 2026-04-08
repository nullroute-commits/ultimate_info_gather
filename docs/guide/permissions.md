# Permissions Analysis

The permissions collector analyzes access levels and available resources.

## PermissionsInfo Model

```python
@dataclass
class PermissionsInfo:
    timestamp: datetime
    permission_level: PermissionLevel
    user_id: int | None
    user_name: str | None
    effective_user_id: int | None
    groups: list[GroupInfo]
    privileged_groups: list[str]
    capabilities: list[CapabilityInfo]
    has_cap_sys_admin: bool
    has_cap_net_admin: bool
    has_cap_dac_override: bool
    fs_permissions: dict[str, FileSystemPermission]
    selinux_enabled: bool
    selinux_context: str | None
    apparmor_enabled: bool
    apparmor_profile: str | None
    can_sudo: bool
    sudo_nopasswd: bool
    resources: ResourceInfo | None
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
```

## Permission Levels

| Level | Description |
|-------|-------------|
| `ROOT` | Running as root (UID 0) |
| `SUDO` | Can elevate via sudo |
| `PRIVILEGED` | Member of privileged groups |
| `STANDARD` | Normal user permissions |
| `RESTRICTED` | Limited permissions |
| `SANDBOXED` | Heavily restricted (seccomp, etc.) |
| `UNKNOWN` | Unable to determine permission level |

## Privileged Groups

These groups grant elevated access:

- `root`, `wheel`, `sudo`, `admin`, `adm`
- `docker`, `lxd`, `libvirt`, `kvm`
- `disk`, `sys`, `shadow`

## Linux Capabilities

The collector checks process capabilities:

| Capability | Purpose |
|------------|---------|
| `CAP_SYS_ADMIN` | Broad system administration |
| `CAP_NET_ADMIN` | Network administration |
| `CAP_DAC_OVERRIDE` | Bypass file permissions |
| `CAP_SYS_PTRACE` | Process tracing |
| `CAP_NET_RAW` | Raw socket access |

## File System Permissions

Critical paths are checked:

```python
CRITICAL_PATHS = [
    '/', '/etc', '/etc/passwd', '/etc/shadow',
    '/etc/sudoers', '/var/log', '/var/run',
    '/tmp', '/root', '/home', '/proc', '/sys',
    '/dev', '/boot', '/usr/bin', '/usr/sbin',
]
```

Each path has access level:

| Level | Description |
|-------|-------------|
| `NONE` | No access |
| `READ` | Read only |
| `WRITE` | Write only |
| `EXECUTE` | Execute only |
| `READ_WRITE` | Read and write |
| `READ_EXECUTE` | Read and execute |
| `WRITE_EXECUTE` | Write and execute |
| `FULL` | Full access (rwx) |

## Security Contexts

### SELinux

- Detected via `/sys/fs/selinux`
- Current context from `/proc/self/attr/current`

### AppArmor

- Detected via `/sys/kernel/security/apparmor`
- Profile from `/proc/self/attr/current`

## Resource Limits

Process limits (ulimits) are captured:

| Limit | Description |
|-------|-------------|
| `max_open_files` | RLIMIT_NOFILE |
| `max_processes` | RLIMIT_NPROC |
| `max_memory` | RLIMIT_AS |
| `max_stack_size` | RLIMIT_STACK |
| `max_cpu_time` | RLIMIT_CPU |
| `max_file_size` | RLIMIT_FSIZE |
| `max_core_size` | RLIMIT_CORE |

## Usage Example

```python
from src.collectors import EnvironmentCollector, PermissionsCollector

async def check_permissions():
    # Get environment first
    env_collector = EnvironmentCollector()
    env_result = await env_collector.safe_collect()
    
    # Pass to permissions collector
    perm_collector = PermissionsCollector(
        environment_state=env_result.data
    )
    perm_result = await perm_collector.safe_collect()
    
    if perm_result.success:
        perms = perm_result.data
        
        print(f"Permission Level: {perms.permission_level.name}")
        print(f"User: {perms.user_name} (UID: {perms.user_id})")
        print(f"Privileged Groups: {perms.privileged_groups}")
        print(f"Can Sudo: {perms.can_sudo}")
        print(f"SELinux: {perms.selinux_enabled}")
        
        # Check specific path
        if '/etc/shadow' in perms.fs_permissions:
            shadow_access = perms.fs_permissions['/etc/shadow']
            print(f"/etc/shadow access: {shadow_access.access_level.name}")
```
