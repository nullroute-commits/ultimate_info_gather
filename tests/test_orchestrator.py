"""
Tests for orchestrator.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
import tempfile

from src.orchestrator import InfoGatherOrchestrator, CollectionPhase, CollectionProgress


@pytest.mark.asyncio
async def test_orchestrator_basic():
    """Test basic orchestrator collection."""
    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()
    
    assert report is not None
    assert report.report_id
    assert report.generated_at
    assert report.generator_version
    assert report.total_collection_time_ms > 0


@pytest.mark.asyncio
async def test_orchestrator_all_phases():
    """Test that all collection phases complete."""
    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()
    
    # All phases should complete (may have errors but should have data)
    assert report.environment is not None
    assert report.permissions is not None
    # Hardware and software may fail in some environments but orchestrator should complete


@pytest.mark.asyncio
async def test_orchestrator_stored_data():
    """Test that data is stored for later use."""
    orchestrator = InfoGatherOrchestrator()
    await orchestrator.collect_all()
    
    # Check stored data
    assert orchestrator.environment_state is not None
    assert orchestrator.permissions_info is not None
    
    # Check get_stored_data method
    stored = orchestrator.get_stored_data()
    assert 'environment' in stored
    assert 'permissions' in stored
    assert 'hardware' in stored
    assert 'software' in stored


@pytest.mark.asyncio
async def test_orchestrator_progress_callback():
    """Test progress callback functionality."""
    progress_updates = []
    
    def callback(progress: CollectionProgress):
        progress_updates.append(progress)
    
    orchestrator = InfoGatherOrchestrator(progress_callback=callback)
    await orchestrator.collect_all()
    
    # Should have received progress updates
    assert len(progress_updates) > 0
    
    # Check progress structure
    for progress in progress_updates:
        assert isinstance(progress.phase, CollectionPhase)
        assert isinstance(progress.status, str)
        assert isinstance(progress.percent_complete, float)
        assert isinstance(progress.elapsed_ms, float)


@pytest.mark.asyncio
async def test_orchestrator_output_generation():
    """Test output file generation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        orchestrator = InfoGatherOrchestrator(output_dir=tmpdir)
        report = await orchestrator.collect_all()
        outputs = await orchestrator.generate_outputs(report)
        
        # Should generate all formats
        assert 'json' in outputs
        assert 'markdown' in outputs
        assert 'text' in outputs
        
        # Files should exist
        for fmt, path in outputs.items():
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0


@pytest.mark.asyncio
async def test_orchestrator_selective_formats():
    """Test generating only selected formats."""
    with tempfile.TemporaryDirectory() as tmpdir:
        orchestrator = InfoGatherOrchestrator(output_dir=tmpdir)
        report = await orchestrator.collect_all()
        outputs = await orchestrator.generate_outputs(report, formats=['json'])
        
        assert 'json' in outputs
        assert 'markdown' not in outputs
        assert 'text' not in outputs


@pytest.mark.asyncio
async def test_report_json_serialization():
    """Test report JSON serialization."""
    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()
    
    json_str = report.to_json()
    assert json_str
    assert '"report_id"' in json_str
    assert '"generated_at"' in json_str


@pytest.mark.asyncio
async def test_report_markdown_generation():
    """Test report Markdown generation."""
    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()
    
    md = report.get_markdown_report()
    assert md
    assert '# System Information Report' in md
    assert '## 🖥️ Environment' in md


@pytest.mark.asyncio
async def test_report_text_summary():
    """Test report text summary generation."""
    orchestrator = InfoGatherOrchestrator()
    report = await orchestrator.collect_all()
    
    summary = report.get_full_summary()
    assert summary
    assert 'SYSTEM INFORMATION REPORT' in summary
    assert 'END OF REPORT' in summary
