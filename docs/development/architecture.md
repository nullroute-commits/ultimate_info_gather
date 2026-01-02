# Architecture

## Overview

Ultimate Info Gather follows a modular, async-first architecture designed for:

- **Extensibility**: Easy to add new collectors
- **Reliability**: Graceful error handling
- **Performance**: Parallel collection where possible
- **Type Safety**: Full type hints throughout

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Orchestrator                          │
│  - Coordinates collection phases                            │
│  - Manages dependencies between collectors                  │
│  - Aggregates results into SystemReport                     │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Environment │  │ Permissions │  │  Hardware   │
│  Collector  │  │  Collector  │  │  Collector  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       │         ┌──────┘                │
       │         │                       │
       ▼         ▼                       ▼
┌─────────────────────────────────────────────────┐
│                   Data Models                    │
│  EnvironmentState, PermissionsInfo, HardwareInfo │
│  SoftwareInfo, SystemReport                      │
└─────────────────────────────────────────────────┘
```

## Base Collector Pattern

All collectors inherit from `BaseCollector`:

```python
class BaseCollector(ABC, Generic[T]):
    """Abstract base for all collectors."""
    
    @abstractmethod
    async def collect(self) -> T:
        """Perform collection - must be implemented."""
        pass
    
    async def safe_collect(self) -> CollectionResult[T]:
        """Safe wrapper with error handling."""
        try:
            result = await self.collect()
            return CollectionResult(success=True, data=result, ...)
        except Exception as e:
            return CollectionResult(success=False, errors=[str(e)], ...)
```

Benefits:
- Consistent error handling
- Duration tracking
- Warning/error aggregation
- Type-safe results

## Dependency Flow

Collections are ordered by data dependencies:

```
Phase 1: Environment
    ↓ (provides execution context)
Phase 2: Permissions (uses Environment)
    ↓ (provides access info)
Phase 3: Hardware + Software (parallel, use both prior)
    ↓
Final: SystemReport aggregation
```

## Async Patterns

### Parallel Collection

```python
async def _collect_hardware_and_software(self):
    hw_task = asyncio.create_task(self._collect_hardware())
    sw_task = asyncio.create_task(self._collect_software())
    return await asyncio.gather(hw_task, sw_task)
```

### Safe Subprocess Execution

```python
async def run_command(self, cmd: list[str], timeout: float = 30.0):
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=timeout,
    )
    return process.returncode, stdout.decode(), stderr.decode()
```

### File Reading

```python
async def read_file_async(self, path: str) -> str | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._read_file_sync, path)
```

## Data Model Design

Models use dataclasses with:

- Full type annotations
- `to_dict()` for serialization
- `get_summary()` for human-readable output
- Enums for categorization

Example:

```python
@dataclass
class HardwareInfo:
    timestamp: datetime
    cpu: CPUInfo | None
    memory: MemoryInfo | None
    # ...
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu": self.cpu.to_dict() if self.cpu else None,
            # ...
        }
```

## Error Handling Strategy

1. **Collector Level**: Individual operations catch exceptions, add warnings
2. **Collection Level**: `safe_collect()` catches overall failures
3. **Orchestrator Level**: Aggregates all errors/warnings in report
4. **Output Level**: Report includes error section

No single failure prevents overall collection.

## Extension Points

### Adding Collectors

1. Create `src/collectors/my_collector.py`
2. Implement `BaseCollector` subclass
3. Create corresponding model
4. Register in orchestrator

### Custom Output Formats

1. Extend `SystemReport` with new method
2. Or create external formatter class
3. Access via `report.to_dict()` for raw data
