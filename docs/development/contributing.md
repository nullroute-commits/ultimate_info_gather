# Contributing

Thank you for your interest in contributing to Ultimate Info Gather!

## Development Setup

1. Fork and clone the repository
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev,docs]"
   ```

## Code Style

The repository is configured for these tools:

- **Ruff** for linting
- **MyPy** for type checking
- **Black** for optional local formatting

Run checks:

```bash
# Lint
ruff check src/ tests/ main.py

# Type check
mypy src/

# Optional formatting
black src/ tests/
```

## Testing

Run the root package tests with pytest:

```bash
# Root package tests
python3 -m pytest tests/ -o addopts=""

# With coverage
python3 -m pytest tests/ --cov=src --cov-report=html -o addopts=""

# Specific test file
python3 -m pytest tests/test_environment.py -o addopts=""

# Verbose output
python3 -m pytest -v tests/ -o addopts=""
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
