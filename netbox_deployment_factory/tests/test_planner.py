"""Unit tests for deployment planning."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from netbox_deployment_factory.planner import build_plan, load_report
from netbox_deployment_factory.renderers import write_bundle

FIXTURE = Path(__file__).parent / "fixtures" / "sample_report.json"


class PlannerTests(unittest.TestCase):
    """Validate planning and rendering decisions."""

    def setUp(self) -> None:
        self.report = load_report(FIXTURE)

    def test_build_plan_uses_small_profile_for_low_memory(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        self.assertEqual(plan.sizing.profile_name, "small")
        self.assertEqual(plan.sizing.netbox_workers, 1)
        self.assertTrue(plan.host.docker_capable)

    def test_device_type_library_profile_is_present(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        self.assertEqual(
            plan.device_type_library.library_repository,
            "https://github.com/netbox-community/devicetype-library.git",
        )
        self.assertEqual(plan.device_type_library.library_ref, "cf50cfe")

    def test_dns_and_proxmox_plugins_are_integrated(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        module_names = [plugin.module_name for plugin in plan.plugins]
        self.assertIn(
            "netbox_dns",
            module_names,
        )
        self.assertIn(
            "netbox_proxbox",
            module_names,
        )

        dns_plugin = next(p for p in plan.plugins if p.module_name == "netbox_dns")
        proxbox_plugin = next(p for p in plan.plugins if p.module_name == "netbox_proxbox")

        self.assertTrue(dns_plugin.enabled)
        self.assertEqual(dns_plugin.package_name, "netbox-plugin-dns")
        self.assertEqual(dns_plugin.version, "1.5.3")

        self.assertFalse(proxbox_plugin.enabled)
        self.assertEqual(proxbox_plugin.package_name, "netbox-proxbox")
        self.assertEqual(proxbox_plugin.version, "0.0.6b2")
        self.assertIn("4.2.99", proxbox_plugin.rationale)

    def test_admin_identity_is_pseudonymous(self) -> None:
        plan = build_plan(
            self.report,
            track="alpine",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        self.assertTrue(plan.admin_privacy.bootstrap_username.startswith("bootstrap-"))
        self.assertTrue(plan.admin_privacy.bootstrap_email.endswith("@invalid.local"))

    def test_bundle_writer_emits_expected_files(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            written = write_bundle(plan, output_dir)
            self.assertGreaterEqual(len(written), 13)
            compose_file = output_dir / "docker-compose.yml"
            plugins_file = output_dir / "configuration" / "plugins.py"
            plan_file = output_dir / "deployment-plan.json"
            importer_file = output_dir / "scripts" / "run-device-type-library-import.sh"
            importer_runner_file = (
                output_dir / "scripts" / "import-device-type-library.py"
            )
            api_token_pepper_file = output_dir / "secrets" / "api_token_pepper_1.example"
            self.assertTrue(compose_file.exists())
            self.assertTrue(plugins_file.exists())
            self.assertTrue(plan_file.exists())
            self.assertTrue(importer_file.exists())
            self.assertTrue(importer_runner_file.exists())
            self.assertTrue(api_token_pepper_file.exists())
            rendered_plan = json.loads(plan_file.read_text(encoding="utf-8"))
            self.assertEqual(rendered_plan["images"]["track"], "debian")
            compose_text = compose_file.read_text(encoding="utf-8")
            netbox_env = (output_dir / "env" / "netbox.env").read_text(
                encoding="utf-8"
            )
            importer_text = importer_file.read_text(encoding="utf-8")
            importer_runner_text = importer_runner_file.read_text(
                encoding="utf-8"
            )
            self.assertIn("bootstrap", netbox_env)
            self.assertIn("DB_PASSWORD_FILE=/run/secrets/db_password", netbox_env)
            self.assertIn(
                "api_token_pepper_1",
                rendered_plan["admin_privacy"]["bootstrap_secret_files"],
            )
            self.assertIn("api_token_pepper_1:", compose_text)
            self.assertIn("condition: service_healthy", compose_text)
            self.assertIn("http://127.0.0.1:8080/login/", compose_text)
            self.assertIn(
                "import-device-type-library.py",
                importer_text,
            )
            self.assertIn("/login/", importer_text)
            self.assertIn(
                'dcim:devicetype_bulk_import',
                importer_runner_text,
            )
            self.assertIn(
                'dcim:manufacturer_bulk_import',
                importer_runner_text,
            )
            self.assertNotIn("Dockerfile-DeviceTypeLibraryImport", compose_text)
            self.assertNotIn("device_type_library_token", compose_text)
            self.assertNotIn("HOUSEKEEPING_INTERVAL=", netbox_env)
            self.assertNotIn("netbox-housekeeping:", compose_text)


if __name__ == "__main__":
    unittest.main()
