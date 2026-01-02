"""
Base collector class and utilities.

Provides common functionality for all async collectors.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar('T')


@dataclass
class CollectionResult(Generic[T]):
    """Result of a collection operation."""
    success: bool
    data: T | None
    duration_ms: float
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class BaseCollector(ABC, Generic[T]):
    """
    Abstract base class for all collectors.
    
    Provides common async utilities and error handling patterns.
    """

    def __init__(self):
        self._errors: list[str] = []
        self._warnings: list[str] = []
        self._start_time: float = 0.0

    @abstractmethod
    async def collect(self) -> T:
        """Perform the collection and return results."""
        pass

    async def safe_collect(self) -> CollectionResult[T]:
        """Safely perform collection with error handling."""
        self._errors = []
        self._warnings = []
        self._start_time = time.perf_counter()

        try:
            result = await self.collect()
            duration = (time.perf_counter() - self._start_time) * 1000
            return CollectionResult(
                success=True,
                data=result,
                duration_ms=duration,
                errors=self._errors.copy(),
                warnings=self._warnings.copy(),
            )
        except Exception as e:
            duration = (time.perf_counter() - self._start_time) * 1000
            self._errors.append(f"Collection failed: {type(e).__name__}: {e}")
            return CollectionResult(
                success=False,
                data=None,
                duration_ms=duration,
                errors=self._errors.copy(),
                warnings=self._warnings.copy(),
            )

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self._errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self._warnings.append(message)

    async def run_command(
        self,
        cmd: list[str],
        timeout: float = 30.0,
        capture_stderr: bool = True,
    ) -> tuple[int, str, str]:
        """
        Run a command asynchronously.
        
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE if capture_stderr else asyncio.subprocess.DEVNULL,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            return (
                process.returncode or 0,
                stdout.decode('utf-8', errors='replace') if stdout else '',
                stderr.decode('utf-8', errors='replace') if stderr else '',
            )
        except TimeoutError:
            self.add_warning(f"Command timed out: {' '.join(cmd)}")
            return (-1, '', 'Command timed out')
        except FileNotFoundError:
            return (-1, '', f'Command not found: {cmd[0]}')
        except Exception as e:
            self.add_warning(f"Command failed: {' '.join(cmd)}: {e}")
            return (-1, '', str(e))

    async def read_file_async(self, path: str, silent_if_missing: bool = False) -> str | None:
        """
        Read a file asynchronously.
        
        Args:
            path: File path to read
            silent_if_missing: If True, don't warn when file doesn't exist or has read errors
                              (useful for optional files like network speed on virtual interfaces)
        """
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._read_file_sync, path)
        except FileNotFoundError:
            if not silent_if_missing:
                self.add_warning(f"Failed to read {path}: [Errno 2] No such file or directory: '{path}'")
            return None
        except OSError as e:
            # Handle specific OS errors like EINVAL (Invalid argument) which can occur
            # when reading sysfs files for virtual network interfaces
            if not silent_if_missing:
                self.add_warning(f"Failed to read {path}: {e}")
            return None
        except Exception as e:
            self.add_warning(f"Failed to read {path}: {e}")
            return None

    def _read_file_sync(self, path: str) -> str:
        """Synchronous file read for executor."""
        with open(path, encoding='utf-8') as f:
            return f.read()

    async def safe_call(
        self,
        func: Callable[[], T],
        default: T,
        error_msg: str = "Operation failed",
    ) -> T:
        """Safely call a function in an executor."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func)
        except Exception as e:
            self.add_warning(f"{error_msg}: {e}")
            return default

    async def gather_with_errors(
        self,
        *coros,
        return_exceptions: bool = True,
    ) -> list[Any]:
        """Gather coroutines and handle exceptions."""
        results = await asyncio.gather(*coros, return_exceptions=return_exceptions)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.add_warning(f"Task {i} failed: {result}")
                results[i] = None

        return results
