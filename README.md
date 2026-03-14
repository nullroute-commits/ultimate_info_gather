# Ultimate Info Gather

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An async Python 3.11+ OOP framework for comprehensive system information collection, permission analysis, and hardware/software inventory.

## Features

- **🔍 Environment Detection**: Captures Python runtime, process info, and execution context
- **🔐 Permission Analysis**: Determines permission levels, capabilities, and resource access
- **🖥️ Hardware Inventory**: Collects CPU, memory, storage, network, and GPU information  
- **📦 Software Inventory**: Catalogs OS, packages, services, containers, and processes
- **⚡ Fully Async**: Built on asyncio for efficient parallel data collection
- **📊 Multiple Output Formats**: JSON, Markdown, and text reports
- **🏗️ OOP Architecture**: Clean, extensible collector-based design

## Requirements

- Python 3.11 or higher
- Linux operating system (primary target)

## Installation

```bash
# Clone the repository
git clone https://github.com/nullroute-commits/ultimate_info_gather.git
cd ultimate_info_gather

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev,docs]"
```

## Quick Start

### Command Line

```bash
# Run full collection
python main.py

# Specify output directory
python main.py -o ./reports

# Select output formats
python main.py -f json markdown

# Verbose output
python main.py -v

# Quiet mode (no progress)
python main.py -q
```

### Programmatic Usage

```python
import asyncio
from src.orchestrator import InfoGatherOrchestrator

async def main():
    # Create orchestrator
    orchestrator = InfoGatherOrchestrator(output_dir='./output')
    
    # Collect all information
    report = await orchestrator.collect_all()
    
    # Access stored data (Objectives 1-3)
    env = orchestrator.environment_state      # Objective 1
    perms = orchestrator.permissions_info     # Objective 2
    hw = orchestrator.hardware_info           # Objective 3
    net = orchestrator.network_info           # Objective 3 (intensive network analysis)
    sw = orchestrator.software_info           # Objective 3
    
    # Generate outputs
    outputs = await orchestrator.generate_outputs(report)
    
    # Print summary
    print(report.get_full_summary())

asyncio.run(main())
```

### Using Individual Collectors

```python
import asyncio
from src.collectors import EnvironmentCollector, PermissionsCollector

async def main():
    # Collect environment info
    env_collector = EnvironmentCollector()
    env_result = await env_collector.safe_collect()
    
    if env_result.success:
        env_state = env_result.data
        print(env_state.get_summary())
        
        # Use environment state for permissions collection
        perm_collector = PermissionsCollector(environment_state=env_state)
        perm_result = await perm_collector.safe_collect()
        
        if perm_result.success:
            print(perm_result.data.get_summary())

asyncio.run(main())
```

## GitHub Copilot Setup

Install and configure GitHub Copilot CLI for AI-powered command-line assistance:

```bash
python3 install_github_copilot.py
```

### Prerequisites

- Python 3.11 or higher
- GitHub Personal Access Token or SSH key in `id_player1` file
- Supported package managers: opkg, apt, dnf, yum, pacman, apk, brew

### Credential File

Create an `id_player1` file containing either:
- GitHub Personal Access Token (recommended)
- SSH private key

Save to one of these locations:
- `./id_player1` (current directory)
- `~/id_player1` (home directory)
- `~/.ssh/id_player1` (SSH directory)

Example:
```bash
# Save token to file
echo "ghp_YourPersonalAccessTokenHere" > ~/id_player1
chmod 600 ~/id_player1
```

### Features

- **Multi-platform support**: Automatically detects and uses the appropriate package manager
- **OpenWrt optimized**: Prioritizes opkg and downloads GitHub CLI binary
- **Async operations**: Fast, efficient installation using Python async/await
- **Authentication**: Automatically configures GitHub authentication
- **Verification**: Validates installation before completing

### Usage

After installation:
```bash
# Get command suggestions
gh copilot suggest "list all files larger than 100MB"

# Explain commands
gh copilot explain "tar -xzf archive.tar.gz"
```

For detailed instructions, see [GitHub Copilot Setup Guide](docs/tools/github-copilot-setup.md).

## Architecture

```
ultimate_info_gather/
├── src/
│   ├── __init__.py
│   ├── orchestrator.py          # Main coordinator
│   ├── models/                   # Data models
│   │   ├── environment.py       # Environment state model
│   │   ├── permissions.py       # Permissions model
│   │   ├── hardware.py          # Hardware model
│   │   ├── network.py           # Network info model
│   │   ├── software.py          # Software model
│   │   └── report.py            # Report aggregation
│   └── collectors/               # Async collectors
│       ├── base.py              # Base collector class
│       ├── environment_collector.py
│       ├── permissions_collector.py
│       ├── hardware_collector.py
│       ├── network_collector.py
│       └── software_collector.py
├── docs/                         # MkDocs documentation
├── tests/                        # Test suite
├── netbox_deployment_factory/    # NetBox deployment bundle generator
├── main.py                       # CLI entry point
└── pyproject.toml               # Project configuration
```

## NetBox Deployment Factory

The [`netbox_deployment_factory/`](netbox_deployment_factory/README.md) subproject is a downstream consumer of `ultimate_info_gather` JSON report output. It generates reproducible NetBox deployment bundles — including Docker Compose configurations, plugin configs, secrets, and bootstrap scripts — from the system information collected by this agent. Refer to [netbox_deployment_factory/README.md](netbox_deployment_factory/README.md) for full usage and configuration details.

## Collection Phases

The orchestrator executes collection in a specific sequence to satisfy data dependencies:

1. **Phase 1 - Environment** (Objective 1)
   - Python environment details
   - Process information
   - Execution mode detection
   - Platform identification

2. **Phase 2 - Permissions** (Objective 2)
   - User/group analysis
   - Linux capabilities
   - File system access levels
   - Security context (SELinux/AppArmor)
   - Resource limits

3. **Phase 3 - Hardware, Network & Software** (Objective 3)
   - Run in parallel for efficiency
   - Hardware: CPU, memory, storage, network, GPU, USB
   - Network: Interfaces, routes, connections, DNS, firewall rules
   - Software: OS, packages, services, containers, processes

## Data Storage

All collected data is stored for later use as specified:

```python
orchestrator = InfoGatherOrchestrator()
report = await orchestrator.collect_all()

# Access stored data
stored = orchestrator.get_stored_data()
# {
#     'environment': EnvironmentState,
#     'permissions': PermissionsInfo,
#     'hardware': HardwareInfo,
#     'network': NetworkInfo,
#     'software': SoftwareInfo,
# }
```

## Documentation

Generate and serve documentation:

```bash
# Install docs dependencies
pip install -e ".[docs]"

# Build documentation
mkdocs build

# Serve locally
mkdocs serve
```

## Testing

```bash
# Run the full root test suite
pytest --tb=short -q

# With coverage details
pytest --cov=src --cov-report=html

# Type checking
mypy src/

# Linting
ruff check src/ tests/ main.py
```

## License

MIT License (declared in `pyproject.toml`).
