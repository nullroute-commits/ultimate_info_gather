# Installation

## Requirements

- **Python**: 3.11 or higher
- **Operating System**: Linux (primary target)
- **Privileges**: Some features require elevated privileges for full data collection

## Install from Source

### Clone Repository

```bash
git clone https://github.com/nullroute-commits/ultimate_info_gather.git
cd ultimate_info_gather
```

### Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### Install Package

=== "Basic Installation"

    ```bash
    pip install -e .
    ```

=== "Development Installation"

    ```bash
    pip install -e ".[dev]"
    ```

=== "With Documentation"

    ```bash
    pip install -e ".[dev,docs]"
    ```

## Verify Installation

```bash
python -c "from src import InfoGatherOrchestrator; print('Installation successful!')"
```

## Optional Dependencies

### For Development

- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `mypy` - Type checking
- `ruff` - Linting
- `black` - Code formatting

### For Documentation

- `mkdocs` - Documentation generator
- `mkdocs-material` - Material theme
- `mkdocstrings` - API documentation

## System Requirements

For full functionality, the following system tools are helpful (but not required):

| Tool | Purpose |
|------|---------|
| `lsusb` | USB device enumeration |
| `lspci` | PCI device enumeration |
| `nvidia-smi` | NVIDIA GPU information |
| `docker`/`podman` | Container information |
| `systemctl` | Service information |

!!! note
    The framework gracefully handles missing tools and will collect as much information as possible.
