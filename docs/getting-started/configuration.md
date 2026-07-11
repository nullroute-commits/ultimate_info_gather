# Configuration

## Orchestrator Options

The `InfoGatherOrchestrator` accepts the following configuration options:

```python
from src.orchestrator import InfoGatherOrchestrator

orchestrator = InfoGatherOrchestrator(
    output_dir='./output',           # Output directory for reports
    progress_callback=my_callback,   # Progress notification callback
)
```

### Output Directory

Specify where report files will be saved:

```python
orchestrator = InfoGatherOrchestrator(output_dir='/var/log/info-gather')
```

### Progress Callback

Receive progress updates during collection:

```python
from src.orchestrator import CollectionProgress, CollectionPhase

def my_callback(progress: CollectionProgress):
    """
    progress.phase: CollectionPhase (ENVIRONMENT, PERMISSIONS, HARDWARE, NETWORK, SOFTWARE)
    progress.status: str - Current status message
    progress.percent_complete: float - 0-100
    progress.elapsed_ms: float - Time elapsed in milliseconds
    """
    if progress.phase == CollectionPhase.HARDWARE:
        print(f"Hardware scan: {progress.status}")

orchestrator = InfoGatherOrchestrator(progress_callback=my_callback)
```

## Output Format Options

Control which formats are generated:

```python
report = await orchestrator.collect_all()

# Generate specific formats
outputs = await orchestrator.generate_outputs(
    report,
    formats=['json', 'markdown']  # Omit 'text'
)
```

Available formats:

| Format | Extension | Description |
|--------|-----------|-------------|
| `json` | `.json` | Structured data for programmatic use |
| `markdown` | `.md` | Human-readable formatted report |
| `text` | `.txt` | Plain text summary |

## Collector Configuration

Individual collectors can be customized by subclassing:

```python
from src.collectors import EnvironmentCollector

class CustomEnvironmentCollector(EnvironmentCollector):
    """Custom environment collector with additional checks."""
    
    async def collect(self):
        # Get base collection
        state = await super().collect()
        
        # Add custom processing
        # ...
        
        return state
```

## Permission Requirements

Some data collection requires elevated privileges:

| Data | Requirement |
|------|-------------|
| Basic environment | None |
| User groups | None |
| Process info | None |
| Capabilities | None |
| `/etc/shadow` access | Root |
| System service control | Root or sudo |
| Kernel module loading | Root |
| Full DMI info | Root |

!!! tip
    Run with `sudo` for complete information collection:
    ```bash
    sudo python3 main.py
    ```

## Environment Variables

The collectors inspect standard environment variables such as:

| Variable | Purpose |
|----------|---------|
| `HOME` | Home directory detection |
| `SHELL` | Shell detection |
| `TERM` | Terminal type |
| `USER` | Current user |
| `PATH` | Executable search paths |

!!! note
    These values are available on the in-memory models and are emitted by the JSON serializers, including `EnvironmentState.environment_variables` and `SoftwareInfo.environment_variables`/`path_directories`.
