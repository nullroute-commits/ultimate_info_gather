# Ultimate Info Gather

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Async Python 3.11+ system inspection for environment, permissions, hardware, network, and software inventory, plus an end-to-end deployment pipeline that can feed the bundled NetBox factory.

## What is here

- **Collector framework**: async collectors for environment, permissions, hardware, network, and software data
- **Report generation**: JSON, Markdown, and text outputs from a unified `SystemReport`
- **Deployment pipeline**: `src/deploy.py` runs collect -> save -> plan -> render -> verify
- **NetBox factory subproject**: `netbox_deployment_factory/` turns a report into a reproducible deployment bundle

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

## Report shape caveats

The in-memory dataclasses are richer than the JSON output in a few places:

- `EnvironmentState.environment_variables` is collected in memory but not currently serialized by `EnvironmentState.to_dict()`.
- `SoftwareInfo.to_dict()` emits counts and samples (`installed_packages_sample`, `system_services_sample`, `running_processes_sample`) rather than the full lists.
- `SoftwareInfo.process_count` currently reflects the number of captured processes, and process capture is capped at 100 entries.

See `docs/guide/reports.md` for the current serialized shape.

## End-to-end deployment pipeline

The root package also ships an async deployment wrapper in `src/deploy.py`:

```bash
# collect -> save report -> plan -> render -> verify
python3 -m src.deploy

# custom output directory
python3 -m src.deploy --output-dir ./deploy_output

# alternate track and deployment name
python3 -m src.deploy --track alpine --deployment-name lab-stack

# Let's Encrypt mode
python3 -m src.deploy --fqdn netbox.example.com --acme-email admin@example.com
```

This root deployment CLI is distinct from the standalone factory CLI in `netbox_deployment_factory/`.

## Repository layout

```text
ultimate_info_gather/
├── src/
│   ├── collectors/
│   ├── models/
│   ├── deploy.py
│   └── orchestrator.py
├── tests/
├── docs/
├── netbox_deployment_factory/
│   ├── src/netbox_deployment_factory/
│   ├── tests/
│   └── README.md
├── install_github_copilot.py
├── main.py
└── pyproject.toml
```

## NetBox deployment factory

`netbox_deployment_factory/` is a separate subproject with its own packaging, tests, and Docker-local workflow. It consumes `ultimate_info_gather` JSON output and generates a NetBox deployment bundle with Compose files, configuration, env files, scripts, and secret placeholders.

Use the subproject README for factory-specific usage:

- [`netbox_deployment_factory/README.md`](netbox_deployment_factory/README.md)
- [`docs/factory/`](docs/factory/index.md)

## GitHub Copilot installer

The repository includes `install_github_copilot.py` for installing GitHub CLI/Copilot helpers across several package-manager environments.

```bash
python3 install_github_copilot.py
```

It looks for an `id_player1` credential file in:

1. `./id_player1`
2. `~/id_player1`
3. `~/.ssh/id_player1`

A personal access token is the most reliable option for gh CLI authentication. An SSH private key can configure git-over-SSH, but it does not fully replace token-based gh authentication.

## Docs

```bash
pip install -e ".[docs]"
mkdocs build
mkdocs serve
```

## Validation

Root package:

```bash
python3 -m pytest tests/ -o addopts=""
ruff check src/ tests/ main.py install_github_copilot.py
mypy src/
```

Factory unit tests:

```bash
cd netbox_deployment_factory
PYTHONPATH=src python3 -m unittest tests.test_planner tests.test_cli
```

## License

MIT.
