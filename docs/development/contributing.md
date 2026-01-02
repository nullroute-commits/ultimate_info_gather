# Contributing

Thank you for your interest in contributing to Ultimate Info Gather!

## Development Setup

1. Fork and clone the repository
2. Create a virtual environment:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev,docs]"
   ```

## Code Style

We use the following tools:

- **Black** for code formatting
- **Ruff** for linting
- **MyPy** for type checking

Run checks:

```bash
# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Testing

Run tests with pytest:

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_environment.py

# Verbose output
pytest -v
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with tests
3. Ensure all checks pass
4. Update documentation if needed
5. Submit PR with clear description

## Adding a New Collector

1. Create collector in `src/collectors/`
2. Inherit from `BaseCollector`
3. Implement `async def collect(self) -> T`
4. Add data model in `src/models/`
5. Update orchestrator if needed
6. Add tests and documentation

Example:

```python
from src.collectors.base import BaseCollector
from src.models.mymodel import MyData

class MyCollector(BaseCollector[MyData]):
    async def collect(self) -> MyData:
        # Implementation
        return MyData(...)
```

## Reporting Issues

Please include:

- Python version
- Operating system
- Full error traceback
- Steps to reproduce
