# Quick Start

This guide will help you get started with Ultimate Info Gather quickly.

## Basic Usage

### Command Line

The simplest way to use Ultimate Info Gather is via the command line:

```bash
python main.py
```

This will:
1. Collect all system information
2. Generate reports in JSON, Markdown, and text formats
3. Save reports to the `./output` directory

### Command Line Options

```bash
# Specify output directory
python main.py -o ./my-reports

# Select specific output formats
python main.py -f json markdown

# Verbose output with full summary
python main.py -v

# Quiet mode (no progress output)
python main.py -q
```

## Programmatic Usage

### Full Collection

```python
import asyncio
from src.orchestrator import InfoGatherOrchestrator

async def main():
    # Create orchestrator with output directory
    orchestrator = InfoGatherOrchestrator(output_dir='./output')
    
    # Collect all information
    report = await orchestrator.collect_all()
    
    # Generate output files
    outputs = await orchestrator.generate_outputs(report)
    
    # Print results
    print(f"Collection completed in {report.total_collection_time_ms:.2f} ms")
    for fmt, path in outputs.items():
        print(f"  {fmt}: {path}")

asyncio.run(main())
```

### Accessing Collected Data

After collection, all data is stored for later use:

```python
async def main():
    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()
    
    # Access environment state (Objective 1)
    env = orchestrator.environment_state
    print(f"Platform: {env.platform_type.name}")
    print(f"Python: {env.python_env.version}")
    print(f"Is Root: {env.is_root}")
    
    # Access permissions info (Objective 2)
    perms = orchestrator.permissions_info
    print(f"Permission Level: {perms.permission_level.name}")
    print(f"Can Sudo: {perms.can_sudo}")
    
    # Access hardware info (Objective 3)
    hw = orchestrator.hardware_info
    if hw.cpu:
        print(f"CPU: {hw.cpu.model_name}")
    
    # Access software info (Objective 3)
    sw = orchestrator.software_info
    print(f"Installed Packages: {len(sw.installed_packages)}")

asyncio.run(main())
```

### Progress Callback

Monitor collection progress with a callback:

```python
from src.orchestrator import InfoGatherOrchestrator, CollectionProgress

def on_progress(progress: CollectionProgress):
    print(f"[{progress.percent_complete:5.1f}%] {progress.phase.name}: {progress.status}")

async def main():
    orchestrator = InfoGatherOrchestrator(
        progress_callback=on_progress
    )
    report = await orchestrator.collect_all()

asyncio.run(main())
```

### Using Individual Collectors

For more control, use collectors directly:

```python
from src.collectors import (
    EnvironmentCollector,
    PermissionsCollector,
    HardwareCollector,
    SoftwareCollector,
)

async def main():
    # Collect environment
    env_collector = EnvironmentCollector()
    env_result = await env_collector.safe_collect()
    
    if env_result.success:
        env_state = env_result.data
        print(env_state.get_summary())
        
        # Pass to permissions collector
        perm_collector = PermissionsCollector(environment_state=env_state)
        perm_result = await perm_collector.safe_collect()
        
        if perm_result.success:
            print(perm_result.data.get_summary())

asyncio.run(main())
```

## Output Formats

### JSON Report

Structured data suitable for programmatic processing:

```json
{
  "report_metadata": {
    "report_id": "uuid",
    "generated_at": "2024-01-01T00:00:00",
    "generator_version": "1.0.0"
  },
  "environment": { ... },
  "permissions": { ... },
  "hardware": { ... },
  "software": { ... }
}
```

### Markdown Report

Human-readable formatted report with tables and sections.

### Text Report

Plain text summary suitable for console output or logging.

## Next Steps

- [Configuration Guide](configuration.md) - Customize collection behavior
- [User Guide](../guide/overview.md) - Detailed usage documentation
- [API Reference](../api/orchestrator.md) - Full API documentation
