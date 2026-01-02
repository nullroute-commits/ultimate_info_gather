# Testing

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_environment.py      # Environment collector tests
├── test_permissions.py      # Permissions collector tests
├── test_hardware.py         # Hardware collector tests
├── test_software.py         # Software collector tests
├── test_orchestrator.py     # Orchestrator tests
├── test_models.py           # Data model tests
└── test_integration.py      # Integration tests
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific file
pytest tests/test_environment.py

# Specific test
pytest tests/test_environment.py::test_platform_detection

# Verbose
pytest -v

# Show print output
pytest -s
```

## Writing Tests

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_environment_collection():
    from src.collectors import EnvironmentCollector
    
    collector = EnvironmentCollector()
    result = await collector.safe_collect()
    
    assert result.success
    assert result.data is not None
    assert result.data.python_env.version
```

### Mocking System Calls

```python
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_with_mocked_command():
    collector = SoftwareCollector()
    
    with patch.object(collector, 'run_command', new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = (0, 'output', '')
        result = await collector.safe_collect()
        
        assert result.success
```

### Mocking File Reads

```python
@pytest.mark.asyncio
async def test_with_mocked_file():
    collector = HardwareCollector()
    
    fake_cpuinfo = """
processor       : 0
model name      : Test CPU
vendor_id       : TestVendor
"""
    
    with patch.object(collector, 'read_file_async', new_callable=AsyncMock) as mock_read:
        mock_read.return_value = fake_cpuinfo
        result = await collector.safe_collect()
        
        assert result.data.cpu.model_name == 'Test CPU'
```

## Test Fixtures

```python
# conftest.py
import pytest
from src.models.environment import EnvironmentState, ExecutionMode, PlatformType

@pytest.fixture
def sample_environment_state():
    return EnvironmentState(
        timestamp=datetime.now(),
        python_env=PythonEnvironment.capture(),
        process_info=ProcessInfo.capture(),
        execution_mode=ExecutionMode.SCRIPT,
        platform_type=PlatformType.LINUX,
        # ... other fields
    )

@pytest.fixture
def sample_permissions_info(sample_environment_state):
    # Create based on environment
    ...
```

## Coverage Requirements

We aim for >80% code coverage:

```bash
# Generate HTML report
pytest --cov=src --cov-report=html

# View in browser
open htmlcov/index.html
```

## CI Integration

Tests run automatically on:

- Pull requests
- Pushes to main branch

GitHub Actions workflow:

```yaml
- name: Run tests
  run: |
    pip install -e ".[dev]"
    pytest --cov=src --cov-report=xml
```
