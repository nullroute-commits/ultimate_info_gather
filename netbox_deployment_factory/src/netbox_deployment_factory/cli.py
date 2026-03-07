"""CLI entry point for deployment bundle generation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .planner import build_plan, load_report
from .renderers import write_bundle


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate a reproducible NetBox deployment bundle from an "
            "ultimate_info_gather report."
        )
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Path to the ultimate_info_gather JSON report.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the deployment bundle should be written.",
    )
    parser.add_argument(
        "--track",
        choices=("alpine", "debian"),
        default="debian",
        help="Image lifecycle track to use.",
    )
    parser.add_argument(
        "--deployment-name",
        default="netbox-stack",
        help="Logical name for the generated deployment.",
    )
    parser.add_argument(
        "--cidr-mode",
        choices=("deterministic", "dynamic"),
        default="deterministic",
        help="CIDR planning mode for generated Docker networks.",
    )
    parser.add_argument(
        "--edge-hosts",
        type=int,
        default=16,
        help="Required host capacity for the edge network in dynamic mode.",
    )
    parser.add_argument(
        "--app-hosts",
        type=int,
        default=16,
        help="Required host capacity for the app network in dynamic mode.",
    )
    parser.add_argument(
        "--data-hosts",
        type=int,
        default=16,
        help="Required host capacity for the data network in dynamic mode.",
    )
    parser.add_argument(
        "--security-hosts",
        type=int,
        default=8,
        help="Required host capacity for the security network in dynamic mode.",
    )
    parser.add_argument(
        "--worker-containers",
        type=int,
        default=None,
        help=(
            "Override the number of NetBox worker containers. "
            "Defaults to the host-derived sizing profile."
        ),
    )
    return parser


def main() -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args()

    report_path = Path(args.report)
    output_dir = Path(args.output_dir)
    report = load_report(report_path)
    plan = build_plan(
        report,
        track=args.track,
        deployment_name=args.deployment_name,
        source_report=report_path,
        cidr_mode=args.cidr_mode,
        required_hosts={
            "edge": args.edge_hosts,
            "app": args.app_hosts,
            "data": args.data_hosts,
            "security": args.security_hosts,
        },
        worker_containers=args.worker_containers,
    )
    written = write_bundle(plan, output_dir)

    print(f"Wrote {len(written)} files to {output_dir}")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
