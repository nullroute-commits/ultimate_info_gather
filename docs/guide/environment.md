# Environment Collection

The environment collector captures information about the Python runtime and execution context.

## EnvironmentState Model

```python
@dataclass
class EnvironmentState:
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
    collection_duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
```

!!! note
    `environment_variables` is collected on the in-memory dataclass and is included in `EnvironmentState.to_dict()`, so it appears in the serialized JSON report.

## Python Environment

Captured Python runtime details:

| Field | Description |
|-------|-------------|
| `version` | Full version string |
| `version_info` | Tuple (major, minor, micro, ...) |
| `implementation` | cpython, pypy, etc. |
| `executable` | Path to Python binary |
| `prefix` | Site packages prefix |
| `base_prefix` | Base prefix (differs in venv) |
| `is_virtual_env` | Running in virtual environment |
| `platform` | sys.platform value |
| `path` | sys.path entries |

## Process Information

Current process details:

| Field | Description |
|-------|-------------|
| `pid` | Process ID |
| `ppid` | Parent process ID |
| `uid` | User ID |
| `gid` | Group ID |
| `euid` | Effective user ID |
| `egid` | Effective group ID |
| `cwd` | Current working directory |
| `argv` | Command line arguments |

## Execution Modes

The collector detects these execution modes:

| Mode | Description |
|------|-------------|
| `INTERACTIVE` | Running in interactive Python shell |
| `SCRIPT` | Running as a script file |
| `MODULE` | Running via `python -m` |
| `SUBPROCESS` | Spawned by another Python process |
| `CONTAINER` | Running inside a container |
| `VIRTUAL_ENV` | Running in a virtual environment |
| `UNKNOWN` | Unable to determine execution mode |

## Platform Types

| Type | Description |
|------|-------------|
| `LINUX` | Linux-based OS |
| `WINDOWS` | Windows OS |
| `MACOS` | macOS / Darwin |
| `BSD` | BSD variants |
| `UNKNOWN` | Unrecognized platform |

## Container Detection

The collector checks for container environments:

- Docker (via `/.dockerenv`)
- Kubernetes (via cgroup markers)
- LXC/LXD containers
- Container environment variables

## WSL Detection

Windows Subsystem for Linux is detected via:

- Kernel release string (`microsoft`, `wsl`)
- `/proc/version` content

## Usage Example

```python
from src.collectors import EnvironmentCollector

async def check_environment():
    collector = EnvironmentCollector()
    result = await collector.safe_collect()
    
    if result.success:
        env = result.data
        
        print(f"Python: {env.python_env.version}")
        print(f"Virtual Env: {env.python_env.is_virtual_env}")
        print(f"Execution Mode: {env.execution_mode.name}")
        print(f"Is Container: {env.is_container}")
        print(f"Is Root: {env.is_root}")
```
