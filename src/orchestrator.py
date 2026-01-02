"""
Main orchestrator for system information gathering.

Coordinates all collectors and produces comprehensive reports.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Any

from .collectors import (
    EnvironmentCollector,
    PermissionsCollector,
    HardwareCollector,
    SoftwareCollector,
)
from .collectors.base import CollectionResult
from .models import (
    EnvironmentState,
    PermissionsInfo,
    HardwareInfo,
    SoftwareInfo,
    SystemReport,
)


class CollectionPhase(Enum):
    """Collection phases."""
    ENVIRONMENT = auto()
    PERMISSIONS = auto()
    HARDWARE = auto()
    SOFTWARE = auto()


@dataclass
class CollectionProgress:
    """Progress information for collection."""
    phase: CollectionPhase
    status: str
    percent_complete: float
    elapsed_ms: float


class InfoGatherOrchestrator:
    """
    Main orchestrator for system information gathering.
    
    Coordinates all collectors in proper sequence, respecting dependencies
    between collection phases, and produces comprehensive reports.
    """
    
    VERSION = "1.0.0"
    
    def __init__(
        self,
        output_dir: Path | str | None = None,
        progress_callback: Callable[[CollectionProgress], None] | None = None,
    ):
        """
        Initialize the orchestrator.
        
        Args:
            output_dir: Directory for output files (default: ./output)
            progress_callback: Optional callback for progress updates
        """
        self.output_dir = Path(output_dir) if output_dir else Path('./output')
        self.progress_callback = progress_callback
        
        # Collection results (stored for later use as per objectives)
        self._environment_state: EnvironmentState | None = None
        self._permissions_info: PermissionsInfo | None = None
        self._hardware_info: HardwareInfo | None = None
        self._software_info: SoftwareInfo | None = None
        
        # Collection metadata
        self._start_time: float = 0.0
        self._errors: list[str] = []
        self._warnings: list[str] = []
    
    @property
    def environment_state(self) -> EnvironmentState | None:
        """Get collected environment state (Objective 1)."""
        return self._environment_state
    
    @property
    def permissions_info(self) -> PermissionsInfo | None:
        """Get collected permissions info (Objective 2)."""
        return self._permissions_info
    
    @property
    def hardware_info(self) -> HardwareInfo | None:
        """Get collected hardware info (Objective 3)."""
        return self._hardware_info
    
    @property
    def software_info(self) -> SoftwareInfo | None:
        """Get collected software info (Objective 3)."""
        return self._software_info
    
    async def collect_all(self) -> SystemReport:
        """
        Perform full system information collection.
        
        Executes all collection phases in sequence, respecting dependencies:
        1. Environment collection (Objective 1)
        2. Permissions collection using environment data (Objective 2)
        3. Hardware & Software collection using prior data (Objective 3)
        
        Returns:
            SystemReport: Complete system information report
        """
        self._start_time = time.perf_counter()
        self._errors = []
        self._warnings = []
        
        report_id = str(uuid.uuid4())
        
        # Phase 1: Environment Collection (Objective 1)
        await self._report_progress(CollectionPhase.ENVIRONMENT, "Collecting environment...", 0.0)
        self._environment_state = await self._collect_environment()
        await self._report_progress(CollectionPhase.ENVIRONMENT, "Complete", 25.0)
        
        # Phase 2: Permissions Collection (Objective 2)
        # Uses environment state from Phase 1
        await self._report_progress(CollectionPhase.PERMISSIONS, "Analyzing permissions...", 25.0)
        self._permissions_info = await self._collect_permissions()
        await self._report_progress(CollectionPhase.PERMISSIONS, "Complete", 50.0)
        
        # Phase 3: Hardware & Software Collection (Objective 3)
        # Uses environment and permissions data from prior phases
        await self._report_progress(CollectionPhase.HARDWARE, "Scanning hardware...", 50.0)
        await self._report_progress(CollectionPhase.SOFTWARE, "Scanning software...", 50.0)
        
        # Hardware and software can run in parallel
        hw_task = asyncio.create_task(self._collect_hardware())
        sw_task = asyncio.create_task(self._collect_software())
        
        self._hardware_info, self._software_info = await asyncio.gather(hw_task, sw_task)
        
        await self._report_progress(CollectionPhase.HARDWARE, "Complete", 100.0)
        await self._report_progress(CollectionPhase.SOFTWARE, "Complete", 100.0)
        
        # Calculate total time
        total_time_ms = (time.perf_counter() - self._start_time) * 1000
        
        # Create report
        report = SystemReport(
            report_id=report_id,
            generated_at=datetime.now(),
            generator_version=self.VERSION,
            environment=self._environment_state,
            permissions=self._permissions_info,
            hardware=self._hardware_info,
            software=self._software_info,
            total_collection_time_ms=total_time_ms,
            collection_errors=self._errors.copy(),
            warnings=self._warnings.copy(),
        )
        
        return report
    
    async def _collect_environment(self) -> EnvironmentState | None:
        """Collect environment information (Objective 1)."""
        collector = EnvironmentCollector()
        result = await collector.safe_collect()
        
        if not result.success:
            self._errors.extend(result.errors)
            return None
        
        self._warnings.extend(result.warnings)
        if result.data:
            result.data.collection_duration_ms = result.duration_ms
        
        return result.data
    
    async def _collect_permissions(self) -> PermissionsInfo | None:
        """Collect permissions information (Objective 2)."""
        # Pass environment state to permissions collector
        collector = PermissionsCollector(environment_state=self._environment_state)
        result = await collector.safe_collect()
        
        if not result.success:
            self._errors.extend(result.errors)
            return None
        
        self._warnings.extend(result.warnings)
        if result.data:
            result.data.collection_duration_ms = result.duration_ms
        
        return result.data
    
    async def _collect_hardware(self) -> HardwareInfo | None:
        """Collect hardware information (Objective 3)."""
        # Pass prior collection results
        collector = HardwareCollector(
            environment_state=self._environment_state,
            permissions_info=self._permissions_info,
        )
        result = await collector.safe_collect()
        
        if not result.success:
            self._errors.extend(result.errors)
            return None
        
        self._warnings.extend(result.warnings)
        if result.data:
            result.data.collection_duration_ms = result.duration_ms
        
        return result.data
    
    async def _collect_software(self) -> SoftwareInfo | None:
        """Collect software information (Objective 3)."""
        # Pass prior collection results
        collector = SoftwareCollector(
            environment_state=self._environment_state,
            permissions_info=self._permissions_info,
        )
        result = await collector.safe_collect()
        
        if not result.success:
            self._errors.extend(result.errors)
            return None
        
        self._warnings.extend(result.warnings)
        if result.data:
            result.data.collection_duration_ms = result.duration_ms
        
        return result.data
    
    async def _report_progress(
        self,
        phase: CollectionPhase,
        status: str,
        percent: float,
    ) -> None:
        """Report collection progress."""
        if self.progress_callback:
            elapsed = (time.perf_counter() - self._start_time) * 1000
            progress = CollectionProgress(
                phase=phase,
                status=status,
                percent_complete=percent,
                elapsed_ms=elapsed,
            )
            self.progress_callback(progress)
    
    async def generate_outputs(
        self,
        report: SystemReport,
        formats: list[str] | None = None,
    ) -> dict[str, Path]:
        """
        Generate output files in various formats.
        
        Args:
            report: The system report to output
            formats: List of formats ('json', 'markdown', 'text')
                    Default: all formats
        
        Returns:
            Dictionary mapping format to output file path
        """
        if formats is None:
            formats = ['json', 'markdown', 'text']
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        outputs: dict[str, Path] = {}
        
        if 'json' in formats:
            json_path = self.output_dir / f'report_{timestamp}.json'
            report.save_json(json_path)
            outputs['json'] = json_path
        
        if 'markdown' in formats:
            md_path = self.output_dir / f'report_{timestamp}.md'
            report.save_markdown(md_path)
            outputs['markdown'] = md_path
        
        if 'text' in formats:
            text_path = self.output_dir / f'report_{timestamp}.txt'
            text_path.write_text(report.get_full_summary())
            outputs['text'] = text_path
        
        return outputs
    
    def get_stored_data(self) -> dict[str, Any]:
        """
        Get all stored collection data.
        
        Returns data stored for later use as per Objectives 1-3.
        """
        return {
            'environment': self._environment_state,
            'permissions': self._permissions_info,
            'hardware': self._hardware_info,
            'software': self._software_info,
        }


async def main():
    """Main entry point for CLI usage."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description='Ultimate Info Gather - System Information Collection'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='./output',
        help='Output directory for reports',
    )
    parser.add_argument(
        '-f', '--format',
        type=str,
        nargs='+',
        choices=['json', 'markdown', 'text'],
        default=['json', 'markdown', 'text'],
        help='Output formats',
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress progress output',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output',
    )
    
    args = parser.parse_args()
    
    def progress_callback(progress: CollectionProgress):
        if not args.quiet:
            print(f"[{progress.percent_complete:5.1f}%] {progress.phase.name}: {progress.status}")
    
    # Create orchestrator
    orchestrator = InfoGatherOrchestrator(
        output_dir=args.output,
        progress_callback=progress_callback if not args.quiet else None,
    )
    
    try:
        # Collect all information
        print("Starting system information collection...")
        print("=" * 60)
        
        report = await orchestrator.collect_all()
        
        print("=" * 60)
        print(f"Collection completed in {report.total_collection_time_ms:.2f} ms")
        
        if report.collection_errors:
            print(f"\nErrors ({len(report.collection_errors)}):")
            for error in report.collection_errors:
                print(f"  - {error}")
        
        # Generate outputs
        outputs = await orchestrator.generate_outputs(report, args.format)
        
        print("\nOutput files:")
        for fmt, path in outputs.items():
            print(f"  {fmt}: {path}")
        
        # Print summary if verbose
        if args.verbose:
            print("\n" + report.get_full_summary())
        
        return 0
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))
