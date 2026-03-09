"""Unit tests for deployment planning."""

from __future__ import annotations

import json
import py_compile
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

    def test_requested_plugins_are_integrated_with_safe_defaults(self) -> None:
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
        self.assertIn("netbox_acls", module_names)
        self.assertIn("netbox_reorder_rack", module_names)
        self.assertIn("netbox_prometheus_sd", module_names)
        self.assertIn("netbox_diode_plugin", module_names)
        self.assertIn("netbox_config_diff", module_names)
        self.assertIn("netbox_floorplan", module_names)
        self.assertIn("netbox_inventory", module_names)

        dns_plugin = next(p for p in plan.plugins if p.module_name == "netbox_dns")
        proxbox_plugin = next(p for p in plan.plugins if p.module_name == "netbox_proxbox")
        acl_plugin = next(p for p in plan.plugins if p.module_name == "netbox_acls")
        reorder_plugin = next(
            p for p in plan.plugins if p.module_name == "netbox_reorder_rack"
        )
        prometheus_plugin = next(
            p for p in plan.plugins if p.module_name == "netbox_prometheus_sd"
        )
        diode_plugin = next(
            p for p in plan.plugins if p.module_name == "netbox_diode_plugin"
        )
        config_diff_plugin = next(
            p for p in plan.plugins if p.module_name == "netbox_config_diff"
        )
        floorplan_plugin = next(
            p for p in plan.plugins if p.module_name == "netbox_floorplan"
        )
        inventory_plugin = next(
            p for p in plan.plugins if p.module_name == "netbox_inventory"
        )

        self.assertTrue(dns_plugin.enabled)
        self.assertEqual(dns_plugin.package_name, "netbox-plugin-dns")
        self.assertEqual(dns_plugin.version, "1.5.3")

        self.assertFalse(proxbox_plugin.enabled)
        self.assertEqual(proxbox_plugin.package_name, "netbox-proxbox")
        self.assertEqual(proxbox_plugin.version, "0.0.6b2")
        self.assertIn("4.2.99", proxbox_plugin.rationale)

        self.assertFalse(acl_plugin.enabled)
        self.assertIn("4.4.99", acl_plugin.rationale)

        self.assertTrue(reorder_plugin.enabled)
        self.assertEqual(reorder_plugin.package_name, "netbox-reorder-rack")

        self.assertFalse(prometheus_plugin.enabled)
        self.assertEqual(prometheus_plugin.package_name, "netbox-prometheus-sd")
        self.assertIn("extras.plugins", prometheus_plugin.rationale)

        self.assertTrue(diode_plugin.enabled)
        self.assertEqual(diode_plugin.package_name, "netboxlabs-diode-netbox-plugin")
        self.assertIn("companion Diode service", diode_plugin.rationale)

        self.assertTrue(config_diff_plugin.enabled)
        self.assertEqual(config_diff_plugin.package_name, "netbox-config-diff")
        self.assertEqual(config_diff_plugin.version, "2.14.0")

        self.assertTrue(floorplan_plugin.enabled)
        self.assertEqual(floorplan_plugin.package_name, "netbox-floorplan-plugin")
        self.assertEqual(floorplan_plugin.version, "0.9.0")

        self.assertTrue(inventory_plugin.enabled)
        self.assertEqual(inventory_plugin.package_name, "netbox-inventory")
        self.assertEqual(inventory_plugin.version, "2.5.0")

    def test_dynamic_network_mode_allocates_subnets(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
            cidr_mode="dynamic",
            required_hosts={
                "edge": 60,
                "app": 30,
                "data": 12,
                "security": 8,
            },
        )

        self.assertEqual(plan.networks.cidr_mode, "dynamic")
        network_map = {segment.name: segment.cidr for segment in plan.networks.segments}
        self.assertEqual(network_map["edge"], "172.31.0.0/26")
        self.assertEqual(network_map["app"], "172.31.0.64/27")
        self.assertEqual(network_map["data"], "172.31.0.96/28")
        self.assertEqual(network_map["security"], "172.31.0.112/28")

    def test_worker_container_override(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
            worker_containers=3,
        )

        self.assertEqual(plan.sizing.netbox_worker_containers, 3)

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
        self.report["environment"]["hostname"] = " localhost "
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            written = write_bundle(plan, output_dir)
            self.assertGreaterEqual(len(written), 16)
            compose_file = output_dir / "docker-compose.yml"
            plugins_file = output_dir / "configuration" / "plugins.py"
            traefik_dynamic_file = output_dir / "configuration" / "traefik" / "dynamic.yml"
            waf_conf_file = output_dir / "configuration" / "waf" / "default.conf"
            orb_orchestration_file = output_dir / "configuration" / "orb" / "orchestration.yml"
            orb_env_file = output_dir / "env" / "orb.env"
            plan_file = output_dir / "deployment-plan.json"
            importer_file = output_dir / "scripts" / "run-device-type-library-import.sh"
            importer_runner_file = (
                output_dir / "scripts" / "import-device-type-library.py"
            )
            cert_script_file = output_dir / "scripts" / "generate-traefik-cert.sh"
            superuser_sync_script_file = output_dir / "scripts" / "sync-superuser.sh"
            orb_agent_script_file = output_dir / "scripts" / "run-orb-agent.sh"
            api_token_pepper_file = output_dir / "secrets" / "api_token_pepper_1.example"
            self.assertTrue(compose_file.exists())
            self.assertTrue(plugins_file.exists())
            self.assertTrue(traefik_dynamic_file.exists())
            self.assertTrue(waf_conf_file.exists())
            self.assertTrue(orb_orchestration_file.exists())
            self.assertTrue(orb_env_file.exists())
            self.assertTrue(plan_file.exists())
            self.assertTrue(importer_file.exists())
            self.assertTrue(importer_runner_file.exists())
            self.assertTrue(cert_script_file.exists())
            self.assertTrue(superuser_sync_script_file.exists())
            self.assertTrue(orb_agent_script_file.exists())
            self.assertTrue(api_token_pepper_file.exists())
            rendered_plan = json.loads(plan_file.read_text(encoding="utf-8"))
            self.assertEqual(rendered_plan["images"]["track"], "debian")
            compose_text = compose_file.read_text(encoding="utf-8")
            plugins_text = plugins_file.read_text(encoding="utf-8")
            netbox_env = (output_dir / "env" / "netbox.env").read_text(
                encoding="utf-8"
            )
            traefik_dynamic_text = traefik_dynamic_file.read_text(encoding="utf-8")
            waf_conf_text = waf_conf_file.read_text(encoding="utf-8")
            orb_orchestration_text = orb_orchestration_file.read_text(encoding="utf-8")
            orb_env_text = orb_env_file.read_text(encoding="utf-8")
            importer_text = importer_file.read_text(encoding="utf-8")
            importer_runner_text = importer_runner_file.read_text(
                encoding="utf-8"
            )
            generated_readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
            superuser_sync_text = superuser_sync_script_file.read_text(encoding="utf-8")
            orb_agent_text = orb_agent_script_file.read_text(encoding="utf-8")
            self.assertIn("bootstrap", netbox_env)
            self.assertIn("DB_PASSWORD_FILE=/run/secrets/db_password", netbox_env)
            self.assertIn(
                "api_token_pepper_1",
                rendered_plan["admin_privacy"]["bootstrap_secret_files"],
            )
            self.assertIn("api_token_pepper_1:", compose_text)
            self.assertIn("condition: service_healthy", compose_text)
            self.assertIn("netbox-worker:", compose_text)
            self.assertIn("      netbox:\n        condition: service_healthy", compose_text)
            self.assertIn("http://127.0.0.1:8080/login/", compose_text)
            self.assertIn("traefik:", compose_text)
            self.assertIn("image: alpine/openssl:latest", compose_text)
            self.assertIn("waf:", compose_text)
            self.assertIn("netbox-superuser-sync:", compose_text)
            self.assertIn("orb-agent:", compose_text)
            self.assertIn("diode:", compose_text)
            self.assertIn("image: netboxlabs/diode-auth:latest", compose_text)
            self.assertIn("diode_target_override", plugins_text)
            self.assertIn("grpc://diode:8080/diode", plugins_text)
            self.assertNotIn('profiles: ["orb"]', compose_text)
            self.assertIn("443:443", compose_text)
            self.assertNotIn("8080:8080", compose_text)
            self.assertIn("netbox-compress", traefik_dynamic_text)
            self.assertIn("proxy_pass http://netbox:8080", waf_conf_text)
            self.assertIn("CSRF_TRUSTED_ORIGINS=", netbox_env)
            self.assertEqual(rendered_plan["networks"]["cidr_mode"], "deterministic")
            self.assertIn(
                "import-device-type-library.py",
                importer_text,
            )
            self.assertIn("/login/", importer_text)
            self.assertIn(
                '/api/dcim/device-types/',
                importer_runner_text,
            )
            self.assertIn(
                '/api/dcim/manufacturers/',
                importer_runner_text,
            )
            py_compile.compile(str(importer_runner_file), doraise=True)
            self.assertIn('NB_SUPERUSER_NAME', superuser_sync_text)
            self.assertIn('get_or_create', superuser_sync_text)
            self.assertIn('orchestration:', orb_orchestration_text)
            self.assertIn('worker_services:', orb_orchestration_text)
            self.assertIn('netbox:', orb_orchestration_text)
            self.assertIn('netbox_plugins:', orb_orchestration_text)
            self.assertIn('ORB_NETBOX_URL=http://netbox:8080', orb_env_text)
            self.assertIn(
                'ORB_ORCHESTRATION_FILE=/etc/netbox/config/orb/orchestration.yml',
                orb_env_text,
            )
            self.assertIn('/login/', orb_agent_text)
            self.assertIn(
                plan.host.hostname.strip(),
                cert_script_file.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                cert_script_file.read_text(encoding="utf-8").count("DNS:localhost"),
                1,
            )
            self.assertIn("## First Start", generated_readme_text)
            self.assertIn("docker compose build", generated_readme_text)
            self.assertIn("copy each `secrets/*.example` file", generated_readme_text)
            self.assertNotIn("Dockerfile-DeviceTypeLibraryImport", compose_text)
            self.assertNotIn("device_type_library_token", compose_text)
            self.assertNotIn("HOUSEKEEPING_INTERVAL=", netbox_env)
            self.assertNotIn("netbox-housekeeping:", compose_text)


if __name__ == "__main__":
    unittest.main()
