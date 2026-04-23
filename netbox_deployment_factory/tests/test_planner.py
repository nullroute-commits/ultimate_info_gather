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
        self.assertEqual(dns_plugin.version, "1.5.5")

        self.assertTrue(proxbox_plugin.enabled)
        self.assertEqual(proxbox_plugin.package_name, "netbox-proxbox")
        self.assertEqual(proxbox_plugin.version, "0.0.10")
        self.assertIn("4.5.x", proxbox_plugin.rationale)

        self.assertTrue(acl_plugin.enabled)
        self.assertIn("4.5.x", acl_plugin.rationale)

        self.assertTrue(reorder_plugin.enabled)
        self.assertEqual(reorder_plugin.package_name, "netbox-reorder-rack")

        self.assertFalse(prometheus_plugin.enabled)
        self.assertEqual(prometheus_plugin.package_name, "netbox-prometheus-sd")
        self.assertIn("extras.plugins", prometheus_plugin.rationale)

        self.assertTrue(diode_plugin.enabled)
        self.assertEqual(diode_plugin.package_name, "netboxlabs-diode-netbox-plugin")
        self.assertIn("Diode auth/ingester/reconciler", diode_plugin.rationale)

        self.assertFalse(config_diff_plugin.enabled)
        self.assertEqual(config_diff_plugin.package_name, "netbox-config-diff")
        self.assertEqual(config_diff_plugin.version, "2.14.2")
        self.assertIn("DuplicatedTypeName", config_diff_plugin.rationale)

        self.assertTrue(floorplan_plugin.enabled)
        self.assertEqual(floorplan_plugin.package_name, "netbox-floorplan-plugin")
        self.assertEqual(floorplan_plugin.version, "0.9.1")

        self.assertTrue(inventory_plugin.enabled)
        self.assertEqual(inventory_plugin.package_name, "netbox-inventory")
        self.assertEqual(inventory_plugin.version, "2.5.1")

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
        self.assertEqual(network_map["monitoring"], "172.31.0.128/27")

    def test_deterministic_network_mode_uses_valid_subnets(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
            cidr_mode="deterministic",
        )

        self.assertEqual(plan.networks.cidr_mode, "deterministic")
        network_map = {segment.name: segment.cidr for segment in plan.networks.segments}
        self.assertEqual(network_map["edge"], "172.30.0.0/27")
        self.assertEqual(network_map["app"], "172.30.0.32/27")
        self.assertEqual(network_map["data"], "172.30.0.64/27")
        self.assertEqual(network_map["security"], "172.30.0.96/28")
        self.assertEqual(network_map["monitoring"], "172.30.0.128/27")

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
        self.assertEqual(dns_plugin.version, "1.5.5")

        self.assertTrue(proxbox_plugin.enabled)
        self.assertEqual(proxbox_plugin.package_name, "netbox-proxbox")
        self.assertEqual(proxbox_plugin.version, "0.0.10")
        self.assertIn("4.5.x", proxbox_plugin.rationale)

    def test_geo_foss_profile_is_present(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        self.assertEqual(
            plan.geo_foss.repository,
            "https://github.com/nullroute-commits/netbox-geo-foss.git",
        )
        self.assertEqual(plan.geo_foss.ref, "50c3c16")
        self.assertEqual(plan.geo_foss.service_name, "netbox-geo-foss")
        self.assertIn("geographic", plan.geo_foss.rationale.lower())

    def test_monitoring_profile_is_present(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        self.assertEqual(
            plan.monitoring.repository,
            "https://github.com/nullroute-commits/enter-the-metrics.git",
        )
        self.assertEqual(plan.monitoring.ref, "706ed92")
        self.assertIn("grafana/grafana:", plan.monitoring.grafana_image)
        self.assertIn("prom/prometheus:", plan.monitoring.prometheus_image)
        self.assertIn("grafana/loki:", plan.monitoring.loki_image)
        self.assertIn("grafana/alloy:", plan.monitoring.alloy_image)
        self.assertIn("balabit/syslog-ng:", plan.monitoring.syslog_ng_image)
        self.assertIn("prom/node-exporter:", plan.monitoring.node_exporter_image)
        self.assertIn("prom/snmp-exporter:", plan.monitoring.snmp_exporter_image)
        self.assertIn("cadvisor/cadvisor:", plan.monitoring.cadvisor_image)
        self.assertIn("monitoring", plan.monitoring.rationale.lower())

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
            traefik_identity_file = (
                output_dir / "configuration" / "traefik" / "dynamic-identity.yml.disabled"
            )
            waf_conf_file = output_dir / "configuration" / "waf" / "default.conf"
            orb_agent_config_file = output_dir / "configuration" / "orb" / "agent.yaml"
            orb_env_file = output_dir / "env" / "orb.env"
            diode_env_file = output_dir / "env" / "diode.env"
            plan_file = output_dir / "deployment-plan.json"
            importer_file = output_dir / "scripts" / "run-device-type-library-import.sh"
            importer_runner_file = (
                output_dir / "scripts" / "import-device-type-library.py"
            )
            cert_script_file = output_dir / "scripts" / "generate-traefik-cert.sh"
            netbox_init_script_file = output_dir / "scripts" / "netbox-init.sh"
            superuser_sync_script_file = output_dir / "scripts" / "sync-superuser.sh"
            diode_ingester_script_file = output_dir / "scripts" / "run-diode-ingester.sh"
            diode_reconciler_script_file = output_dir / "scripts" / "run-diode-reconciler.sh"
            diode_credential_setup_file = output_dir / "scripts" / "setup-diode-credential.sh"
            api_token_pepper_file = output_dir / "secrets" / "api_token_pepper_1.example"
            self.assertTrue(compose_file.exists())
            self.assertTrue(plugins_file.exists())
            self.assertTrue(traefik_dynamic_file.exists())
            self.assertTrue(traefik_identity_file.exists())
            self.assertTrue(waf_conf_file.exists())
            self.assertTrue(orb_agent_config_file.exists())
            self.assertTrue(orb_env_file.exists())
            self.assertTrue(diode_env_file.exists())
            self.assertTrue(plan_file.exists())
            self.assertTrue(importer_file.exists())
            self.assertTrue(importer_runner_file.exists())
            self.assertTrue(cert_script_file.exists())
            self.assertTrue(netbox_init_script_file.exists())
            self.assertTrue(superuser_sync_script_file.exists())
            self.assertTrue(diode_ingester_script_file.exists())
            self.assertTrue(diode_reconciler_script_file.exists())
            self.assertTrue(diode_credential_setup_file.exists())
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
            orb_agent_config_text = orb_agent_config_file.read_text(encoding="utf-8")
            orb_env_text = orb_env_file.read_text(encoding="utf-8")
            diode_env_text = diode_env_file.read_text(encoding="utf-8")
            importer_text = importer_file.read_text(encoding="utf-8")
            importer_runner_text = importer_runner_file.read_text(
                encoding="utf-8"
            )
            generated_readme_text = (output_dir / "README.md").read_text(encoding="utf-8")
            superuser_sync_text = superuser_sync_script_file.read_text(encoding="utf-8")
            diode_ingester_text = diode_ingester_script_file.read_text(encoding="utf-8")
            diode_reconciler_text = diode_reconciler_script_file.read_text(encoding="utf-8")
            self.assertIn("bootstrap", netbox_env)
            self.assertIn("DB_PASSWORD_FILE=/run/secrets/db_password", netbox_env)
            self.assertIn(
                "api_token_pepper_1",
                rendered_plan["admin_privacy"]["bootstrap_secret_files"],
            )
            self.assertEqual(
                rendered_plan["adjacent_services"][0]["primary_solution"], "Authentik"
            )
            self.assertEqual(
                rendered_plan["adjacent_services"][1]["primary_solution"], "Vaultwarden"
            )
            self.assertIn("api_token_pepper_1:", compose_text)
            self.assertIn("condition: service_healthy", compose_text)
            self.assertIn("netbox-worker:", compose_text)
            self.assertIn("      netbox:\n        condition: service_healthy", compose_text)
            self.assertIn("http://127.0.0.1:8080/login/", compose_text)
            self.assertIn("traefik:", compose_text)
            self.assertIn("image: alpine/openssl:3.5.5", compose_text)
            self.assertIn("waf:", compose_text)
            self.assertIn("netbox-init:", compose_text)
            self.assertIn("orb-agent:", compose_text)
            self.assertIn("orb-bootstrap:", compose_text)
            # orb-bootstrap depends on hydra-bootstrap-clients to ensure client is registered
            self.assertIn("hydra-bootstrap-clients", compose_text)
            # orb-agent depends on orb-bootstrap completing before it starts
            self.assertIn("orb-config:", compose_text)
            # orb-agent reads from the runtime-patched volume, not the raw config dir
            self.assertIn("orb-config:/opt/orb:ro", compose_text)
            self.assertNotIn("./configuration/orb:/opt/orb:ro", compose_text)
            self.assertIn("diode-auth:", compose_text)
            self.assertIn("diode-ingester:", compose_text)
            self.assertIn("diode-proxy:", compose_text)
            self.assertIn("image: nginx:1.27-alpine", compose_text)
            self.assertIn('"127.0.0.1:18084:80"', compose_text)
            self.assertIn("diode-reconciler:", compose_text)
            self.assertIn("image: netboxlabs/diode-auth:1.12.0", compose_text)
            self.assertIn('"127.0.0.1:18080:8080"', compose_text)
            # diode-proxy nginx config must be generated
            diode_proxy_conf = (output_dir / "configuration" / "diode-proxy.conf")
            self.assertTrue(diode_proxy_conf.exists())
            diode_proxy_conf_text = diode_proxy_conf.read_text(encoding="utf-8")
            self.assertIn("location = /auth/token", diode_proxy_conf_text)
            self.assertIn("proxy_pass http://diode-auth:8080/token", diode_proxy_conf_text)
            self.assertIn("grpc_pass grpc://diode-ingester:8081", diode_proxy_conf_text)
            self.assertIn("diode_target_override", plugins_text)
            self.assertIn("grpc://diode-auth:8080/diode", plugins_text)
            self.assertIn('profiles: ["orb-discovery"]', compose_text)
            self.assertIn('command: ["run", "-c", "/opt/orb/agent.yaml"]', compose_text)
            # orb-agent requires host-level network access for scanning
            self.assertIn("network_mode: host", compose_text)
            self.assertIn("NET_ADMIN", compose_text)
            self.assertIn("NET_RAW", compose_text)
            # service_ip from fixture: eth0 (1000 Mbps) wins over eth1 (100 Mbps)
            self.assertEqual(plan.host.service_ip, "10.0.0.50")
            self.assertIn("10.0.0.50:443:443", compose_text)
            self.assertIn("IP:10.0.0.50", cert_script_file.read_text(encoding="utf-8"))
            self.assertIn("10.0.0.50", netbox_env)  # ALLOWED_HOSTS
            self.assertIn("https://10.0.0.50", netbox_env)  # CSRF_TRUSTED_ORIGINS
            self.assertNotIn('"8080:8080"', compose_text)
            self.assertIn("netbox-compress", traefik_dynamic_text)
            self.assertNotIn("authentik-forward-auth", traefik_dynamic_text)
            traefik_identity_text = traefik_identity_file.read_text(encoding="utf-8")
            self.assertIn("authentik-forward-auth", traefik_identity_text)
            self.assertIn("netbox-sso", traefik_identity_text)
            self.assertIn("proxy_pass $netbox_upstream", waf_conf_text)
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
            # orb-bootstrap.sh injects secret at runtime; populate-env-secrets.sh no longer
            # needs to touch agent.yaml
            orb_bootstrap_file = output_dir / "scripts" / "orb-bootstrap.sh"
            self.assertTrue(orb_bootstrap_file.exists())
            orb_bootstrap_text = orb_bootstrap_file.read_text(encoding="utf-8")
            self.assertIn("diode_client_secret", orb_bootstrap_text)
            self.assertIn("client_secret: replace-me", orb_bootstrap_text)
            self.assertIn("agent.yaml", orb_bootstrap_text)
            populate_env_text = (
                output_dir / "scripts" / "populate-env-secrets.sh"
            ).read_text(encoding="utf-8")
            self.assertNotIn("ORB_AGENT_YAML", populate_env_text)
            self.assertNotIn("configuration/orb/agent.yaml", populate_env_text)
            self.assertIn("orb-bootstrap container", populate_env_text)
            self.assertIn('config_manager:', orb_agent_config_text)
            self.assertIn('network_discovery:', orb_agent_config_text)
            self.assertIn('grpc://127.0.0.1:18084', orb_agent_config_text)
            self.assertIn('client_id: netbox-to-diode', orb_agent_config_text)
            self.assertIn('client_secret: replace-me', orb_agent_config_text)
            self.assertIn('dry_run: false', orb_agent_config_text)
            self.assertIn('schedule: "@every 120m"', orb_agent_config_text)
            self.assertIn('timeout: 1800', orb_agent_config_text)
            self.assertIn('-sS', orb_agent_config_text)
            self.assertIn('-sV', orb_agent_config_text)
            self.assertIn('-O', orb_agent_config_text)
            self.assertNotIn('schedule: "@every 5m"', orb_agent_config_text)
            self.assertIn('scope:', orb_agent_config_text)
            self.assertIn('targets:', orb_agent_config_text)
            self.assertIn('10.0.0.0/8', orb_agent_config_text)
            self.assertIn('172.16.0.0/12', orb_agent_config_text)
            self.assertIn('192.168.0.0/16', orb_agent_config_text)
            self.assertIn('DIODE_TARGET=grpc://127.0.0.1:18084', orb_env_text)
            self.assertIn('REDIS_HOST=valkey', diode_env_text)
            self.assertIn('REDIS_PASSWORD=replace-me', diode_env_text)
            self.assertIn('POSTGRES_PASSWORD=replace-me', diode_env_text)
            self.assertIn('DIODE_AUTH_TOKEN_URL=http://diode-auth:8080/token', diode_env_text)
            self.assertIn('NETBOX_DIODE_PLUGIN_API_BASE_URL=', diode_env_text)
            self.assertIn(
                'REDIS_PASSWORD="$(cat /run/secrets/diode_redis_password)"',
                diode_ingester_text,
            )
            self.assertIn('DIODE_TO_NETBOX_CLIENT_SECRET', diode_reconciler_text)
            # diode credential setup assertions
            diode_credential_setup_text = diode_credential_setup_file.read_text(encoding="utf-8")
            self.assertIn('diode', diode_credential_setup_text)
            self.assertIn('get_or_create', diode_credential_setup_text)
            self.assertIn('Token', diode_credential_setup_text)
            # diode-credential-setup is now called from netbox-init; no longer its own service
            self.assertNotIn('diode-credential-setup:', compose_text)
            netbox_init_text = netbox_init_script_file.read_text(encoding="utf-8")
            self.assertIn('sync-superuser.sh', netbox_init_text)
            self.assertIn('setup-diode-credential.sh', netbox_init_text)
            self.assertIn(
                plan.host.hostname.strip(),
                cert_script_file.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                cert_script_file.read_text(encoding="utf-8").count("DNS:localhost"),
                1,
            )
            self.assertIn("## First Start", generated_readme_text)
            self.assertIn("## Recommended Adjacent FOSS Services", generated_readme_text)
            self.assertIn("Authentik", generated_readme_text)
            self.assertIn("Vaultwarden", generated_readme_text)
            self.assertIn("Linkding", generated_readme_text)
            self.assertIn("Nextcloud", generated_readme_text)
            self.assertIn("@every 120m", generated_readme_text)
            self.assertIn("docker compose build", generated_readme_text)
            self.assertIn("Populate secrets", generated_readme_text)
            self.assertIn("openssl rand", generated_readme_text)
            # geo-foss assertions
            geo_foss_env_file = output_dir / "env" / "geo-foss.env"
            geo_foss_dockerfile = output_dir / "Dockerfile-GeoFoss"
            self.assertTrue(geo_foss_env_file.exists())
            self.assertTrue(geo_foss_dockerfile.exists())
            geo_foss_env_text = geo_foss_env_file.read_text(encoding="utf-8")
            geo_foss_dockerfile_text = geo_foss_dockerfile.read_text(encoding="utf-8")
            self.assertIn("GEONAMES_USERNAME=", geo_foss_env_text)
            self.assertIn("NETBOX_URL=", geo_foss_env_text)
            self.assertIn("netbox-geo-foss:", compose_text)
            self.assertIn('profiles: ["geo-foss-import"]', compose_text)
            self.assertIn("dockerfile: Dockerfile-GeoFoss", compose_text)
            self.assertIn("geo-foss-cache:", compose_text)
            self.assertIn("token-store:", compose_text)
            self.assertIn("50c3c16", geo_foss_dockerfile_text)
            self.assertIn("## Geographic Data", generated_readme_text)
            # geo-foss import script
            import_script = output_dir / "scripts" / "import-geo-data.py"
            self.assertTrue(import_script.exists())
            import_script_text = import_script.read_text(encoding="utf-8")
            self.assertIn("import pynetbox", import_script_text)
            self.assertIn("FALLBACK_COUNTRIES", import_script_text)
            # sync script writes full v2 token
            sync_script = output_dir / "scripts" / "sync-superuser.sh"
            sync_text = sync_script.read_text(encoding="utf-8")
            self.assertIn("/token-store/api_token", sync_text)
            self.assertNotIn("Dockerfile-DeviceTypeLibraryImport", compose_text)
            self.assertNotIn("device_type_library_token", compose_text)
            self.assertNotIn("HOUSEKEEPING_INTERVAL=", netbox_env)
            self.assertNotIn("netbox-housekeeping:", compose_text)
            # monitoring stack assertions
            monitoring_prometheus_config = (
                output_dir / "configuration" / "monitoring" / "prometheus" / "prometheus.yml"
            )
            monitoring_loki_config = (
                output_dir / "configuration" / "monitoring" / "loki" / "loki-config.yml"
            )
            monitoring_alloy_config = (
                output_dir / "configuration" / "monitoring" / "alloy" / "config.alloy"
            )
            monitoring_syslog_ng_config = (
                output_dir / "configuration" / "monitoring" / "syslog-ng" / "syslog-ng.conf"
            )
            grafana_prometheus_ds = (
                output_dir
                / "configuration"
                / "monitoring"
                / "grafana"
                / "provisioning"
                / "datasources"
                / "prometheus.yml"
            )
            grafana_loki_ds = (
                output_dir
                / "configuration"
                / "monitoring"
                / "grafana"
                / "provisioning"
                / "datasources"
                / "loki.yml"
            )
            grafana_dashboard_prov = (
                output_dir
                / "configuration"
                / "monitoring"
                / "grafana"
                / "provisioning"
                / "dashboards"
                / "performance_overview.yml"
            )
            monitoring_env_file = output_dir / "env" / "monitoring.env"
            monitoring_dashboard_script = output_dir / "scripts" / "fetch-monitoring-dashboards.sh"
            self.assertTrue(monitoring_prometheus_config.exists())
            self.assertTrue(monitoring_loki_config.exists())
            self.assertTrue(monitoring_alloy_config.exists())
            self.assertTrue(monitoring_syslog_ng_config.exists())
            self.assertTrue(grafana_prometheus_ds.exists())
            self.assertTrue(grafana_loki_ds.exists())
            self.assertTrue(grafana_dashboard_prov.exists())
            self.assertTrue(monitoring_env_file.exists())
            self.assertTrue(monitoring_dashboard_script.exists())
            prometheus_config_text = monitoring_prometheus_config.read_text(encoding="utf-8")
            self.assertIn("scrape_configs:", prometheus_config_text)
            self.assertIn("prometheus:9090", prometheus_config_text)
            self.assertIn("grafana:3000", prometheus_config_text)
            self.assertIn("cadvisor:8080", prometheus_config_text)
            self.assertIn("netbox:8080", prometheus_config_text)
            self.assertIn("snmp-exporter:9116", prometheus_config_text)
            self.assertIn("metrics_path: /metrics", prometheus_config_text)
            loki_config_text = monitoring_loki_config.read_text(encoding="utf-8")
            self.assertIn("http_listen_port: 3100", loki_config_text)
            self.assertIn("reporting_enabled: false", loki_config_text)
            alloy_config_text = monitoring_alloy_config.read_text(encoding="utf-8")
            self.assertIn("loki:3100", alloy_config_text)
            self.assertIn("syslog", alloy_config_text)
            self.assertIn("0.0.0.0:5514", alloy_config_text)
            syslog_ng_text = monitoring_syslog_ng_config.read_text(encoding="utf-8")
            self.assertIn("127.0.0.1", syslog_ng_text)
            self.assertIn("5514", syslog_ng_text)
            grafana_prom_ds_text = grafana_prometheus_ds.read_text(encoding="utf-8")
            self.assertIn("prometheus:9090", grafana_prom_ds_text)
            grafana_loki_ds_text = grafana_loki_ds.read_text(encoding="utf-8")
            self.assertIn("loki:3100", grafana_loki_ds_text)
            grafana_dashboard_prov_text = grafana_dashboard_prov.read_text(encoding="utf-8")
            self.assertIn("PerformanceOverviewDashboards", grafana_dashboard_prov_text)
            monitoring_env_text = monitoring_env_file.read_text(encoding="utf-8")
            self.assertIn("GF_ANALYTICS_REPORTING_ENABLED=false", monitoring_env_text)
            dashboard_script_text = monitoring_dashboard_script.read_text(encoding="utf-8")
            self.assertIn("706ed92", dashboard_script_text)
            self.assertIn("performance_overview_docker.json", dashboard_script_text)
            # monitoring compose services
            self.assertIn('profiles: ["monitoring"]', compose_text)
            self.assertIn("grafana:", compose_text)
            self.assertIn("prometheus:", compose_text)
            self.assertIn("loki:", compose_text)
            self.assertIn("alloy:", compose_text)
            self.assertIn("syslog-ng:", compose_text)
            self.assertIn("node-exporter:", compose_text)
            self.assertIn("pid: host", compose_text)
            self.assertIn("snmp-exporter:", compose_text)
            self.assertIn("cadvisor:", compose_text)
            self.assertIn("monitoring-dashboard-init:", compose_text)
            self.assertIn("grafana-data:", compose_text)
            self.assertIn("grafana-dashboards:", compose_text)
            self.assertIn("prometheus-data:", compose_text)
            self.assertIn("monitoring:", compose_text)
            # host-networked services for host/LAN input
            self.assertIn("node-exporter:host-gateway", compose_text)
            self.assertIn("snmp-exporter:host-gateway", compose_text)
            self.assertIn("127.0.0.1:5514:5514", compose_text)
            self.assertIn("## Monitoring Stack", generated_readme_text)
            self.assertIn("enter-the-metrics", generated_readme_text)
            # security-observability assertions
            self.assertIn("wazuh-manager:", compose_text)
            self.assertIn("wazuh/wazuh-manager:4.14.4", compose_text)
            self.assertIn("wazuh-agent:", compose_text)
            self.assertIn("wazuh/wazuh-agent:4.14.4", compose_text)
            self.assertIn('profiles: ["security-observability"]', compose_text)
            self.assertIn("WAZUH_MANAGER_SERVER", compose_text)
            self.assertIn("wazuh-remoted", compose_text)
            self.assertIn("wazuh-manager-data:", compose_text)

    def test_letsencrypt_tls_profile(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
            fqdn="netbox.example.com",
            acme_email="admin@example.com",
        )

        self.assertEqual(plan.tls.mode, "letsencrypt")
        self.assertEqual(plan.tls.fqdn, "netbox.example.com")
        self.assertEqual(plan.tls.acme_email, "admin@example.com")
        self.assertEqual(plan.tls.dns_provider, "cloudflare")

    def test_self_signed_tls_profile_default(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        self.assertEqual(plan.tls.mode, "self_signed")
        self.assertIsNone(plan.tls.fqdn)

    def test_letsencrypt_requires_acme_email(self) -> None:
        with self.assertRaises(ValueError):
            build_plan(
                self.report,
                track="debian",
                deployment_name="test-stack",
                source_report=FIXTURE,
                fqdn="netbox.example.com",
            )

    def test_letsencrypt_bundle_output(self) -> None:
        plan = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
            fqdn="netbox.example.com",
            acme_email="admin@example.com",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            write_bundle(plan, output_dir)
            compose_text = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")
            traefik_dynamic_text = (
                output_dir / "configuration" / "traefik" / "dynamic.yml"
            ).read_text(encoding="utf-8")
            netbox_env = (output_dir / "env" / "netbox.env").read_text(encoding="utf-8")
            cert_script_path = output_dir / "scripts" / "generate-traefik-cert.sh"
            cf_token_example = output_dir / "secrets" / "cf_dns_api_token.example"

            # Compose should have ACME config, not self-signed certgen
            self.assertNotIn("traefik-certgen", compose_text)
            self.assertNotIn("alpine/openssl", compose_text)
            self.assertIn("certificatesresolvers.letsencrypt.acme", compose_text)
            self.assertIn("dnschallenge.provider=cloudflare", compose_text)
            self.assertIn("admin@example.com", compose_text)
            self.assertIn("acme-data:", compose_text)
            self.assertIn("cf_dns_api_token", compose_text)
            self.assertNotIn("traefik-certs:", compose_text)
            # Port 80 should be published for HTTP-to-HTTPS redirect
            self.assertIn(":80:80", compose_text)

            # Traefik dynamic config should reference certResolver, not static certs
            self.assertNotIn("certFile:", traefik_dynamic_text)
            self.assertNotIn("keyFile:", traefik_dynamic_text)
            self.assertIn("certResolver: letsencrypt", traefik_dynamic_text)
            self.assertIn("netbox.example.com", traefik_dynamic_text)

            # NetBox env should include the FQDN
            self.assertIn("netbox.example.com", netbox_env)
            self.assertIn("https://netbox.example.com", netbox_env)

            # Self-signed cert script should NOT be written
            self.assertFalse(cert_script_path.exists())

            # Cloudflare token secret example should be written
            self.assertTrue(cf_token_example.exists())


    def test_version_pins_use_latest_major(self) -> None:
        """All infrastructure images must be pinned with explicit tags and
        use the latest major release for each component."""

        plan = build_plan(
            self.report,
            track="alpine",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            write_bundle(plan, output_dir)
            compose_text = (output_dir / "docker-compose.yml").read_text(encoding="utf-8")

            # --- No floating tags allowed ---
            self.assertNotIn(":latest", compose_text)
            self.assertNotIn(":nginx\n", compose_text)

            # --- PostgreSQL pinned to 18 (latest major) ---
            self.assertIn("postgres:18-alpine", compose_text)
            self.assertEqual(plan.images.postgres_image, "postgres:18-alpine")

            # --- Valkey pinned to 9 (latest major) ---
            self.assertIn("valkey/valkey:9-alpine", compose_text)
            self.assertEqual(plan.images.valkey_image, "valkey/valkey:9-alpine")

            # --- Grafana pinned to 12.x (latest major) ---
            self.assertIn("grafana/grafana:12.", compose_text)

            # --- Loki and Alloy pinned to latest stable ---
            self.assertIn("grafana/loki:3.", compose_text)
            self.assertIn("grafana/alloy:v1.", compose_text)

            # --- Alloy image is pinned to exact version ---
            from netbox_deployment_factory.constants import ALLOY_IMAGE
            self.assertEqual(plan.monitoring.alloy_image, ALLOY_IMAGE)

            # --- Prometheus pinned to v3.x (latest major) ---
            self.assertIn("prom/prometheus:v3.", compose_text)

            # --- Traefik pinned to specific patch, not just minor ---
            self.assertRegex(compose_text, r"traefik:v3\.\d+\.\d+")

            # --- OWASP CRS pinned with version, not bare backend tag ---
            self.assertRegex(compose_text, r"owasp/modsecurity-crs:4\.\d+\.\d+-nginx")

            # --- Authentik pinned to 2026 (latest major) ---
            self.assertIn("2026.", plan.identity.authentik_image)

            # --- Identity Postgres matches main Postgres major ---
            main_pg_major = plan.images.postgres_image.split(":")[1].split("-")[0]
            # Identity postgres is used for Authentik and Hydra
            self.assertIn(f"postgres:{main_pg_major}", compose_text)

        # --- Debian track follows the same major versions ---
        plan_deb = build_plan(
            self.report,
            track="debian",
            deployment_name="test-stack",
            source_report=FIXTURE,
        )
        self.assertEqual(plan_deb.images.postgres_image, "postgres:18")
        self.assertEqual(plan_deb.images.valkey_image, "valkey/valkey:9")


if __name__ == "__main__":
    unittest.main()
