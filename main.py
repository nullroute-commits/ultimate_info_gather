#!/usr/bin/env python3
"""
Ultimate Info Gather - Main Entry Point

Async Python 3.11+ system information collection framework.
"""

import asyncio
import sys

from src.orchestrator import main

if __name__ == '__main__':

    sys.exit(asyncio.run(main()))
