"""Tests for the async deployment wrapper."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# Ensure netbox_deployment_factory is importable
import sys

NDF_SRC = str(
    Path(__file__).resolve().parents[1] / "netbox_deployment_factory" / "src"
)
if NDF_SRC not in sys.path:
    sys.path.insert(0, NDF_SRC)

from src.deploy import (
    DeploymentResult,
    DeployPhase,
    PhaseResult,
    _verify_bundle,
    run_deployment,
)


# ---------------------------------------------------------------------------
# Full pipeline test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_deployment_succeeds_end_to_end() -> None:
    """Full pipeline: collect → save → plan → render → verify."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)

        assert isinstance(result, DeploymentResult)
        assert result.success, (
            f"Pipeline failed.\n"
            f"  Failures: {result.verification_failures}\n"
            f"  Phases: {[(p.phase.name, p.success, p.message) for p in result.phases]}"
        )
        assert len(result.phases) == 5
        assert result.report_path is not None
        assert result.report_path.exists()
        assert result.bundle_dir is not None
        assert result.bundle_dir.exists()
        assert result.elapsed_ms > 0


@pytest.mark.asyncio
async def test_all_phases_succeed() -> None:
    """Each individual phase must report success."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)

        phase_names = [p.phase for p in result.phases]
        assert phase_names == [
            DeployPhase.COLLECT,
            DeployPhase.SAVE_REPORT,
            DeployPhase.PLAN,
            DeployPhase.RENDER,
            DeployPhase.VERIFY,
        ]
        for pr in result.phases:
            assert pr.success, f"{pr.phase.name} failed: {pr.message}"
            assert pr.duration_ms >= 0


# ---------------------------------------------------------------------------
# Phase-detail tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_collect_phase_returns_report_data() -> None:
    """COLLECT phase should produce a valid JSON report on disk."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)
        assert result.report_path is not None

        report = json.loads(result.report_path.read_text(encoding="utf-8"))
        assert "report_metadata" in report
        assert "environment" in report
        assert "hardware" in report
        assert "network" in report
        assert "software" in report


@pytest.mark.asyncio
async def test_plan_phase_details() -> None:
    """PLAN phase details should include sizing and plugin counts."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)

        plan_phase = next(p for p in result.phases if p.phase == DeployPhase.PLAN)
        assert "profile" in plan_phase.details
        assert plan_phase.details["plugins_enabled"] > 0
        assert plan_phase.details["networks"] >= 6
        assert plan_phase.details["tls_mode"] in ("self_signed", "letsencrypt")


@pytest.mark.asyncio
async def test_render_phase_file_count() -> None:
    """RENDER phase must write a reasonable number of files."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)

        render_phase = next(p for p in result.phases if p.phase == DeployPhase.RENDER)
        assert render_phase.details["file_count"] >= 16


# ---------------------------------------------------------------------------
# Verification coverage tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bundle_compose_has_all_services() -> None:
    """Compose file must reference every expected service."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)
        assert result.bundle_dir is not None

        compose = (result.bundle_dir / "docker-compose.yml").read_text(encoding="utf-8")
        for svc in (
            "traefik:", "waf:", "postgres:", "valkey:", "netbox:",
            "netbox-worker:", "netbox-superuser-sync:",
            "diode-auth:", "diode-ingester:", "diode-reconciler:",
            "diode-credential-setup:",
            "device-type-library-import:", "netbox-geo-foss:",
            "orb-agent:", "wazuh-agent:",
            "grafana:", "prometheus:", "loki:", "promtail:", "syslog-ng:",
            "node-exporter:", "snmp-exporter:", "cadvisor:",
            "authentik-server:", "authentik-worker:", "authentik-postgres:",
            "hydra:", "hydra-postgres:", "hydra-migrate:",
            "hydra-bootstrap-clients:",
        ):
            assert svc in compose, f"compose missing service: {svc}"


@pytest.mark.asyncio
async def test_bundle_network_segments_valid() -> None:
    """All network CIDRs in the plan must be valid IPv4 networks."""

    import ipaddress

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)
        assert result.bundle_dir is not None

        plan = json.loads(
            (result.bundle_dir / "deployment-plan.json").read_text(encoding="utf-8")
        )
        segments = plan["networks"]["segments"]
        assert len(segments) >= 6

        for seg in segments:
            net = ipaddress.IPv4Network(seg["cidr"], strict=True)
            assert net.num_addresses >= 2


@pytest.mark.asyncio
async def test_bundle_plugins_enabled() -> None:
    """Enabled plugins must appear in plugin_requirements.txt."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)
        assert result.bundle_dir is not None

        reqs = (result.bundle_dir / "plugin_requirements.txt").read_text(encoding="utf-8")
        for pkg in (
            "netbox-topology-views",
            "netbox-bgp",
            "netbox-plugin-dns",
            "netbox-reorder-rack",
            "netboxlabs-diode-netbox-plugin",
            "netbox-config-diff",
            "netbox-floorplan-plugin",
            "netbox-inventory",
        ):
            assert pkg in reqs, f"plugin_requirements.txt missing: {pkg}"


@pytest.mark.asyncio
async def test_verify_bundle_standalone() -> None:
    """_verify_bundle should return no failures for a good bundle."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)
        assert result.bundle_dir is not None

        failures = await _verify_bundle(result.bundle_dir)
        assert failures == [], f"Unexpected failures: {failures}"


@pytest.mark.asyncio
async def test_verify_bundle_detects_missing_file() -> None:
    """_verify_bundle must flag missing required files."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir)
        assert result.bundle_dir is not None

        # Remove a required file
        (result.bundle_dir / "docker-compose.yml").unlink()
        failures = await _verify_bundle(result.bundle_dir)
        assert any("docker-compose.yml" in f for f in failures)


# ---------------------------------------------------------------------------
# Option forwarding tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alpine_track() -> None:
    """Alpine track should propagate to the plan."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir, track="alpine")
        assert result.success
        assert result.bundle_dir is not None

        plan = json.loads(
            (result.bundle_dir / "deployment-plan.json").read_text(encoding="utf-8")
        )
        assert plan["images"]["track"] == "alpine"
        assert "alpine" in plan["images"]["postgres_image"]


@pytest.mark.asyncio
async def test_worker_container_override() -> None:
    """Worker container override should appear in plan."""

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir, worker_containers=3)
        assert result.success
        assert result.bundle_dir is not None

        plan = json.loads(
            (result.bundle_dir / "deployment-plan.json").read_text(encoding="utf-8")
        )
        assert plan["sizing"]["netbox_worker_containers"] == 3


@pytest.mark.asyncio
async def test_progress_callback_called() -> None:
    """Progress callback should be invoked during collection."""

    calls: list[object] = []

    def _cb(p: object) -> None:
        calls.append(p)

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_deployment(output_dir=tmpdir, progress_callback=_cb)
        assert result.success
        assert len(calls) > 0
