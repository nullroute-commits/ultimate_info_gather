"""Tests for the async deployment wrapper."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure netbox_deployment_factory is importable without changing import precedence
NDF_SRC = str(
    Path(__file__).resolve().parents[1] / "netbox_deployment_factory" / "src"
)
if NDF_SRC not in sys.path:
    sys.path.append(NDF_SRC)

from src.deploy import (  # noqa: E402
    DeploymentResult,
    DeployPhase,
    _verify_bundle,
    run_deployment,
)

# ---------------------------------------------------------------------------
# Shared fixture – runs the pipeline once, reused across read-only tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _shared_deployment_dir():
    """Temporary directory that persists for the entire test module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="module")
def shared_result(_shared_deployment_dir):
    """Run the pipeline once and share the result across tests."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            run_deployment(output_dir=str(_shared_deployment_dir))
        )
    finally:
        loop.close()
    return result


# ---------------------------------------------------------------------------
# Full pipeline test (independent run to prove idempotent success)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_deployment_succeeds_end_to_end() -> None:
    """Full pipeline: collect -> save -> plan -> render -> verify."""

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


# ---------------------------------------------------------------------------
# Phase-detail tests (reuse shared result)
# ---------------------------------------------------------------------------

def test_all_phases_succeed(shared_result: DeploymentResult) -> None:
    """Each individual phase must report success."""

    phase_names = [p.phase for p in shared_result.phases]
    assert phase_names == [
        DeployPhase.COLLECT,
        DeployPhase.SAVE_REPORT,
        DeployPhase.PLAN,
        DeployPhase.RENDER,
        DeployPhase.VERIFY,
    ]
    for pr in shared_result.phases:
        assert pr.success, f"{pr.phase.name} failed: {pr.message}"
        assert pr.duration_ms >= 0


def test_collect_phase_returns_report_data(shared_result: DeploymentResult) -> None:
    """COLLECT phase should produce a valid JSON report on disk."""

    assert shared_result.report_path is not None

    report = json.loads(shared_result.report_path.read_text(encoding="utf-8"))
    assert "report_metadata" in report
    assert "environment" in report
    assert "hardware" in report
    assert "network" in report
    assert "software" in report


def test_plan_phase_details(shared_result: DeploymentResult) -> None:
    """PLAN phase details should include sizing and plugin counts."""

    plan_phase = next(p for p in shared_result.phases if p.phase == DeployPhase.PLAN)
    assert "profile" in plan_phase.details
    assert plan_phase.details["plugins_enabled"] > 0
    assert plan_phase.details["networks"] >= 6
    assert plan_phase.details["tls_mode"] in ("self_signed", "letsencrypt")


def test_render_phase_file_count(shared_result: DeploymentResult) -> None:
    """RENDER phase must write a reasonable number of files."""

    render_phase = next(p for p in shared_result.phases if p.phase == DeployPhase.RENDER)
    assert render_phase.details["file_count"] >= 16


# ---------------------------------------------------------------------------
# Verification coverage tests (reuse shared result)
# ---------------------------------------------------------------------------

def test_bundle_compose_has_all_services(shared_result: DeploymentResult) -> None:
    """Compose file must reference every expected service."""

    assert shared_result.bundle_dir is not None

    compose = (shared_result.bundle_dir / "docker-compose.yml").read_text(encoding="utf-8")
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


def test_bundle_network_segments_valid(shared_result: DeploymentResult) -> None:
    """All network CIDRs in the plan must be valid IPv4 networks."""

    import ipaddress

    assert shared_result.bundle_dir is not None

    plan = json.loads(
        (shared_result.bundle_dir / "deployment-plan.json").read_text(encoding="utf-8")
    )
    segments = plan["networks"]["segments"]
    assert len(segments) >= 6

    for seg in segments:
        net = ipaddress.IPv4Network(seg["cidr"], strict=True)
        assert net.num_addresses >= 2


def test_bundle_plugins_enabled(shared_result: DeploymentResult) -> None:
    """Enabled plugins must appear in plugin_requirements.txt."""

    assert shared_result.bundle_dir is not None

    reqs = (shared_result.bundle_dir / "plugin_requirements.txt").read_text(encoding="utf-8")
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
