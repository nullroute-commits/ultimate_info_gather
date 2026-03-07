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
    )
    written = write_bundle(plan, output_dir)

    print(f"Wrote {len(written)} files to {output_dir}")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
