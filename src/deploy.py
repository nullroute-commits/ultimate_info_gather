"""
Async deployment orchestrator.

Chains system information collection with NetBox deployment bundle
generation and validates that every generated feature is operational.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Phase / result models
# ---------------------------------------------------------------------------

class DeployPhase(Enum):
    """Phases of the deployment pipeline."""

    COLLECT = auto()
    SAVE_REPORT = auto()
    PLAN = auto()
    RENDER = auto()
    VERIFY = auto()


@dataclass
class PhaseResult:
    """Outcome of a single deployment phase."""

    phase: DeployPhase
    success: bool
    duration_ms: float
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentResult:
    """Aggregate result returned by :func:`run_deployment`."""

    success: bool
    phases: list[PhaseResult]
    report_path: Path | None = None
    bundle_dir: Path | None = None
    verification_failures: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0


# ---------------------------------------------------------------------------
# Feature verification helpers
# ---------------------------------------------------------------------------

# Files that must exist in every generated bundle.
_REQUIRED_BUNDLE_FILES: list[str] = [
    "docker-compose.yml",
    "Dockerfile-Plugins",
    "Dockerfile-GeoFoss",
    "plugin_requirements.txt",
    "deployment-plan.json",
    "README.md",
    "configuration/extra.py",
    "configuration/plugins.py",
    "configuration/traefik/dynamic.yml",
    "configuration/waf/default.conf",
    "configuration/orb/agent.yaml",
    "configuration/monitoring/prometheus/prometheus.yml",
    "configuration/monitoring/loki/loki-config.yml",
    "configuration/monitoring/promtail/promtail-config.yml",
    "configuration/monitoring/syslog-ng/syslog-ng.conf",
    "configuration/monitoring/grafana/provisioning/datasources/prometheus.yml",
    "configuration/monitoring/grafana/provisioning/datasources/loki.yml",
    "configuration/monitoring/grafana/provisioning/dashboards/performance_overview.yml",
    "env/netbox.env",
    "env/postgres.env",
    "env/diode.env",
    "env/authentik.env",
    "env/hydra.env",
    "env/orb.env",
    "env/device-type-library-import.env",
    "env/geo-foss.env",
    "env/monitoring.env",
    "scripts/sync-superuser.sh",
    "scripts/run-device-type-library-import.sh",
    "scripts/import-device-type-library.py",
    "scripts/run-diode-ingester.sh",
    "scripts/run-diode-reconciler.sh",
    "scripts/setup-diode-credential.sh",
    "scripts/authentik-bootstrap-netbox.sh",
    "scripts/run-geo-foss-import.sh",
    "scripts/import-geo-data.py",
    "scripts/fetch-monitoring-dashboards.sh",
    "secrets/.gitignore",
]

# Compose service names that must appear as top-level service keys.
_COMPOSE_SERVICES: list[str] = [
    "traefik",
    "waf",
    "postgres",
    "valkey",
    "netbox",
    "netbox-worker",
    "netbox-superuser-sync",
    "diode-auth",
    "diode-ingester",
    "diode-reconciler",
    "diode-credential-setup",
    "device-type-library-import",
    "netbox-geo-foss",
    "wazuh-agent",
    "orb-agent",
    "grafana",
    "prometheus",
    "loki",
    "promtail",
    "syslog-ng",
    "node-exporter",
    "snmp-exporter",
    "cadvisor",
    "authentik-server",
    "authentik-worker",
    "authentik-postgres",
    "authentik-bootstrap-netbox",
    "hydra",
    "hydra-postgres",
    "hydra-migrate",
    "hydra-bootstrap-clients",
    "monitoring-dashboard-init",
]

# Additional compose-level features verified by plain substring match.
_COMPOSE_EXTRA_MARKERS: dict[str, str] = {
    "healthcheck": "condition: service_healthy",
    "scoped-networks": "subnet:",
}

# Plan-level features to verify in deployment-plan.json.
_PLAN_FEATURES: dict[str, list[str]] = {
    "sizing": ["sizing.profile_name"],
    "images": ["images.netbox_image", "images.postgres_image", "images.valkey_image"],
    "plugins": ["plugins"],
    "networks": ["networks.segments"],
    "admin_privacy": ["admin_privacy.bootstrap_username"],
    "device_type_library": ["device_type_library.library_repository"],
    "geo_foss": ["geo_foss.repository"],
    "monitoring": ["monitoring.repository"],
    "identity": ["identity.authentik_image", "identity.hydra_image"],
    "tls": ["tls.mode"],
    "adjacent_services": ["adjacent_services"],
}


def _resolve_dotted(data: dict[str, Any], dotted_key: str) -> Any:
    """Walk *data* following a dotted key path."""
    parts = dotted_key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


async def _verify_bundle(bundle_dir: Path) -> list[str]:
    """Return a list of verification failure messages (empty == all good)."""

    failures: list[str] = []

    # 1. Required files -------------------------------------------------------
    for rel in _REQUIRED_BUNDLE_FILES:
        full = bundle_dir / rel
        if not full.exists():
            failures.append(f"missing file: {rel}")
        elif full.stat().st_size == 0:
            failures.append(f"empty file: {rel}")

    # Self-signed bundles need the cert script; LE bundles need the CF token
    cert_script = bundle_dir / "scripts" / "generate-traefik-cert.sh"
    cf_example = bundle_dir / "secrets" / "cf_dns_api_token.example"
    if not cert_script.exists() and not cf_example.exists():
        failures.append(
            "missing TLS artefact: neither generate-traefik-cert.sh nor "
            "cf_dns_api_token.example found"
        )

    # 2. Compose features ------------------------------------------------------
    compose_path = bundle_dir / "docker-compose.yml"
    if compose_path.exists():
        compose_text = compose_path.read_text(encoding="utf-8")
        for svc in _COMPOSE_SERVICES:
            pattern = rf"^\s+{re.escape(svc)}:\s*$"
            if not re.search(pattern, compose_text, re.MULTILINE):
                failures.append(f"compose missing service: {svc}")
        for feature, marker in _COMPOSE_EXTRA_MARKERS.items():
            if marker not in compose_text:
                failures.append(f"compose missing feature: {feature} (marker: {marker!r})")
    else:
        failures.append("docker-compose.yml not found – skipping compose checks")

    # 3. Plan features ---------------------------------------------------------
    plan_path = bundle_dir / "deployment-plan.json"
    plan_data: dict[str, Any] = {}
    if plan_path.exists():
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(f"deployment-plan.json is not valid JSON: {exc}")
        else:
            for feature, keys in _PLAN_FEATURES.items():
                for key in keys:
                    value = _resolve_dotted(plan_data, key)
                    if value is None:
                        failures.append(
                            f"plan missing feature: {feature} (key: {key})"
                        )
    else:
        failures.append("deployment-plan.json not found – skipping plan checks")

    # 4. Plugin requirements ---------------------------------------------------
    req_path = bundle_dir / "plugin_requirements.txt"
    if req_path.exists():
        req_text = req_path.read_text(encoding="utf-8")
        expected_pkgs = [
            "netbox-topology-views",
            "netbox-bgp",
            "netbox-plugin-dns",
            "netbox-reorder-rack",
            "netboxlabs-diode-netbox-plugin",
            "netbox-config-diff",
            "netbox-floorplan-plugin",
            "netbox-inventory",
        ]
        for pkg in expected_pkgs:
            if pkg not in req_text:
                failures.append(f"plugin_requirements.txt missing: {pkg}")

    # 5. Network segments in plan have valid CIDRs -----------------------------
    if plan_path.exists():
        import ipaddress

        for seg in plan_data.get("networks", {}).get("segments", []):
            try:
                ipaddress.IPv4Network(seg["cidr"], strict=True)
            except (ValueError, KeyError) as exc:
                failures.append(
                    f"invalid network CIDR for segment {seg.get('name', '?')}: {exc}"
                )

    return failures


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

async def run_deployment(
    *,
    output_dir: Path | str = "./deploy_output",
    deployment_name: str = "netbox-stack",
    track: str = "debian",
    cidr_mode: str = "deterministic",
    required_hosts: dict[str, int] | None = None,
    worker_containers: int | None = None,
    host_ip: str | None = None,
    fqdn: str | None = None,
    acme_email: str | None = None,
    progress_callback: Any | None = None,
) -> DeploymentResult:
    """
    End-to-end async deployment pipeline.

    1. **COLLECT** – gather live system information via :class:`InfoGatherOrchestrator`.
    2. **SAVE_REPORT** – persist the JSON report.
    3. **PLAN** – feed the report into :func:`build_plan`.
    4. **RENDER** – emit the full deployment bundle via :func:`write_bundle`.
    5. **VERIFY** – confirm every expected feature is present and correct.

    Returns a :class:`DeploymentResult` with per-phase details and any
    verification failures.
    """

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    phases: list[PhaseResult] = []
    wall_start = time.perf_counter()

    report_dict: dict[str, Any] = {}
    report_path: Path | None = None
    bundle_dir = output / "bundle"

    # --- Phase 1: COLLECT ---------------------------------------------------
    t0 = time.perf_counter()
    try:
        from .orchestrator import InfoGatherOrchestrator

        orchestrator = InfoGatherOrchestrator(
            output_dir=str(output / "reports"),
            progress_callback=progress_callback,
        )
        report = await orchestrator.collect_all()
        report_dict = report.to_dict()
        phases.append(PhaseResult(
            phase=DeployPhase.COLLECT,
            success=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message="System information collected",
            details={"errors": report.collection_errors, "warnings": report.warnings},
        ))
    except Exception as exc:
        phases.append(PhaseResult(
            phase=DeployPhase.COLLECT,
            success=False,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Collection failed: {exc}",
        ))
        return DeploymentResult(
            success=False,
            phases=phases,
            elapsed_ms=(time.perf_counter() - wall_start) * 1000,
        )

    # --- Phase 2: SAVE_REPORT -----------------------------------------------
    t0 = time.perf_counter()
    try:
        report_path = output / "reports" / "report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        def _write_report() -> None:
            report_path.write_text(  # type: ignore[union-attr]
                json.dumps(report_dict, indent=2, default=str),
                encoding="utf-8",
            )

        await asyncio.to_thread(_write_report)
        phases.append(PhaseResult(
            phase=DeployPhase.SAVE_REPORT,
            success=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Report saved to {report_path}",
        ))
    except Exception as exc:
        phases.append(PhaseResult(
            phase=DeployPhase.SAVE_REPORT,
            success=False,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Report save failed: {exc}",
        ))
        return DeploymentResult(
            success=False,
            phases=phases,
            report_path=report_path,
            elapsed_ms=(time.perf_counter() - wall_start) * 1000,
        )

    # --- Phase 3: PLAN ------------------------------------------------------
    t0 = time.perf_counter()
    try:
        # Import inside the function so the top-level module stays dependency-free
        # when netbox_deployment_factory is not installed.
        from netbox_deployment_factory.planner import build_plan  # type: ignore[import-untyped]

        assert report_path is not None
        saved_report_path: Path = report_path

        plan = await asyncio.to_thread(
            build_plan,
            report_dict,
            track,
            deployment_name,
            saved_report_path,
            cidr_mode,
            required_hosts or {},
            worker_containers,
            host_ip,
            fqdn,
            acme_email,
        )
        phases.append(PhaseResult(
            phase=DeployPhase.PLAN,
            success=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Deployment plan built ({plan.sizing.profile_name} profile)",
            details={
                "profile": plan.sizing.profile_name,
                "workers": plan.sizing.netbox_worker_containers,
                "plugins_enabled": sum(1 for p in plan.plugins if p.enabled),
                "plugins_total": len(plan.plugins),
                "networks": len(plan.networks.segments),
                "tls_mode": plan.tls.mode,
            },
        ))
    except Exception as exc:
        phases.append(PhaseResult(
            phase=DeployPhase.PLAN,
            success=False,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Plan generation failed: {exc}",
        ))
        return DeploymentResult(
            success=False,
            phases=phases,
            report_path=report_path,
            elapsed_ms=(time.perf_counter() - wall_start) * 1000,
        )

    # --- Phase 4: RENDER ----------------------------------------------------
    t0 = time.perf_counter()
    try:
        from netbox_deployment_factory.renderers import write_bundle  # type: ignore[import-untyped]

        written = await asyncio.to_thread(write_bundle, plan, bundle_dir)
        phases.append(PhaseResult(
            phase=DeployPhase.RENDER,
            success=True,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Bundle rendered – {len(written)} files written to {bundle_dir}",
            details={"file_count": len(written)},
        ))
    except Exception as exc:
        phases.append(PhaseResult(
            phase=DeployPhase.RENDER,
            success=False,
            duration_ms=(time.perf_counter() - t0) * 1000,
            message=f"Bundle rendering failed: {exc}",
        ))
        return DeploymentResult(
            success=False,
            phases=phases,
            report_path=report_path,
            bundle_dir=bundle_dir,
            elapsed_ms=(time.perf_counter() - wall_start) * 1000,
        )

    # --- Phase 5: VERIFY ----------------------------------------------------
    t0 = time.perf_counter()
    failures = await _verify_bundle(bundle_dir)
    phases.append(PhaseResult(
        phase=DeployPhase.VERIFY,
        success=len(failures) == 0,
        duration_ms=(time.perf_counter() - t0) * 1000,
        message=(
            "All features verified"
            if not failures
            else f"{len(failures)} verification failure(s)"
        ),
        details={"failures": failures},
    ))

    elapsed = (time.perf_counter() - wall_start) * 1000
    return DeploymentResult(
        success=len(failures) == 0,
        phases=phases,
        report_path=report_path,
        bundle_dir=bundle_dir,
        verification_failures=failures,
        elapsed_ms=elapsed,
    )


# ---------------------------------------------------------------------------
# Convenience CLI
# ---------------------------------------------------------------------------

def _build_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run end-to-end deployment: collect → plan → render → verify",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default="./deploy_output",
        help="Root output directory (default: ./deploy_output)",
    )
    parser.add_argument(
        "--deployment-name",
        default="netbox-stack",
        help="Logical name for the generated deployment.",
    )
    parser.add_argument(
        "--track",
        choices=("alpine", "debian"),
        default="debian",
        help="Image lifecycle track.",
    )
    parser.add_argument(
        "--cidr-mode",
        choices=("deterministic", "dynamic"),
        default="deterministic",
        help="CIDR planning mode.",
    )
    parser.add_argument(
        "--worker-containers",
        type=int,
        default=None,
        help="Override worker container count.",
    )
    parser.add_argument(
        "--host-ip",
        default=None,
        help="Override the detected host IP.",
    )
    parser.add_argument(
        "--fqdn",
        default=None,
        help="FQDN for Let's Encrypt TLS.",
    )
    parser.add_argument(
        "--acme-email",
        default=None,
        help="ACME email (required with --fqdn).",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    return parser


async def _async_main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    from .orchestrator import CollectionProgress

    def _progress(p: CollectionProgress) -> None:
        if not args.quiet:
            print(f"  [{p.percent_complete:5.1f}%] {p.phase.name}: {p.status}")

    print("=" * 60)
    print("  Async Deployment Pipeline")
    print("=" * 60)

    result = await run_deployment(
        output_dir=args.output_dir,
        deployment_name=args.deployment_name,
        track=args.track,
        cidr_mode=args.cidr_mode,
        worker_containers=args.worker_containers,
        host_ip=args.host_ip,
        fqdn=args.fqdn,
        acme_email=args.acme_email,
        progress_callback=_progress if not args.quiet else None,
    )

    print()
    for pr in result.phases:
        status = "✅" if pr.success else "❌"
        print(f"  {status} {pr.phase.name:<15} {pr.duration_ms:>8.1f} ms – {pr.message}")

    print()
    if result.verification_failures:
        print("  Verification failures:")
        for f in result.verification_failures:
            print(f"    • {f}")
        print()

    overall = "SUCCESS" if result.success else "FAILED"
    print(f"  Pipeline {overall} in {result.elapsed_ms:.1f} ms")
    if result.bundle_dir:
        print(f"  Bundle: {result.bundle_dir}")
    if result.report_path:
        print(f"  Report: {result.report_path}")
    print("=" * 60)

    return 0 if result.success else 1


def main() -> int:
    """Synchronous entry point for ``python -m src.deploy``."""
    return asyncio.run(_async_main())


if __name__ == "__main__":
    sys.exit(main())
