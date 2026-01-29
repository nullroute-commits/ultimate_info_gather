#!/usr/bin/env python3
"""
Ultimate Info Gather - Main Entry Point

Async Python 3.9+ system information collection framework.
"""

import asyncio
import sys

from src.orchestrator import main

if __name__ == '__main__':
    if sys.version_info < (3, 9):
        print("Error: Python 3.9 or higher is required", file=sys.stderr)
        sys.exit(1)
    
    sys.exit(asyncio.run(main()))
