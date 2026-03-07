"""CLI smoke tests."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_report.json"
ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    """Validate the CLI end-to-end."""

    def test_cli_generates_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "bundle"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "netbox_deployment_factory",
                    "--report",
                    str(FIXTURE),
                    "--output-dir",
                    str(output_dir),
                    "--track",
                    "debian",
                    "--deployment-name",
                    "cli-bundle",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue((output_dir / "docker-compose.yml").exists())
            self.assertIn("Wrote", result.stdout)


if __name__ == "__main__":
    unittest.main()
