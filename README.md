# Ultimate Info Gather

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Async Python 3.11+ system inspection for environment, permissions, hardware, network, and software inventory.

## What is here

- **Collector framework**: async collectors for environment, permissions, hardware, network, and software data
- **Report generation**: JSON, Markdown, and text outputs from a unified `SystemReport`
- **Python API and CLI**: reusable orchestration through `src.orchestrator` and `main.py`

## Requirements

- Python 3.11+
- Linux as the primary target platform

## Install

```bash
git clone https://github.com/nullroute-commits/ultimate_info_gather.git
cd ultimate_info_gather
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev,docs]"
```

## Run the collector

```bash
# Full collection to ./output
python3 main.py

# Custom output directory
python3 main.py -o ./reports

# Only selected formats
python3 main.py -f json markdown

# Full summary to stdout
python3 main.py -v

# Suppress progress output
python3 main.py -q
```

After `pip install`, the equivalent `info-gather` console command is also available:

```bash
info-gather -o ./reports -f json markdown
```

## Use it from Python

```python
import asyncio
from src.orchestrator import InfoGatherOrchestrator


async def main():
    orchestrator = InfoGatherOrchestrator(output_dir="./output")
    report = await orchestrator.collect_all()

    print(report.get_full_summary())

    # Stored phase results remain available on the orchestrator
    env = orchestrator.environment_state
    perms = orchestrator.permissions_info
    hw = orchestrator.hardware_info
    net = orchestrator.network_info
    sw = orchestrator.software_info

    await orchestrator.generate_outputs(report, ["json", "markdown"])


asyncio.run(main())
```

## Report shape

The JSON output is a complete serialization of the in-memory dataclasses:

- `EnvironmentState.environment_variables` is serialized by `EnvironmentState.to_dict()`.
- `SoftwareInfo.to_dict()` emits full inventories (`installed_packages`, `system_services`, `running_processes`) alongside the `*_count` fields, plus `environment_variables` and `path_directories`.
- `running_processes` entries carry real per-process telemetry read from `/proc` (`cpu_percent`, `memory_percent`, `memory_bytes`, `num_threads`, `create_time`, `cwd`), and `system_services` entries are enriched via `systemctl show` (`is_enabled`, `pid`, `user`, `start_time`, `memory_bytes`, `cpu_percent`).
- `SoftwareInfo.process_count` reflects the number of captured processes; processes are captured in ascending PID order and capture is capped at 100 entries.

See `docs/guide/reports.md` for the serialized shape.

## Repository layout

```text
ultimate_info_gather/
├── src/
│   ├── collectors/
│   ├── models/
│   └── orchestrator.py
├── tests/
├── docs/
├── main.py
└── pyproject.toml
```

## GitHub Copilot installer

The GitHub Copilot installer script has been moved to a private repository and is no longer distributed here.

## Docs

```bash
pip install -e ".[docs]"
mkdocs build
mkdocs serve
```

## Agent skill and source of truth

- `/agent.md` is the canonical Agency/GitHub Copilot-compatible repository
  skill and source of truth for verified capabilities, known gaps, and roadmap
- `docs/agent.md` is the published documentation mirror
- When behavior changes, keep both files aligned with the implementation

## Validation

```bash
python3 -m pytest tests/ -o addopts=""
ruff check src/ tests/ main.py
mypy src/
```

## License

MIT.
