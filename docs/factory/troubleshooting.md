# Troubleshooting

Common issues and operational tips for the NetBox Deployment Factory.

## First Boot Issues

### NetBox stays in "Starting" state

**Symptom**: After `docker compose up -d`, the NetBox container stays in a starting or unhealthy state for more than 10 minutes.

**Cause**: NetBox runs database migrations on first boot, which can be slow on hosts with limited resources.

**Resolution**:

1. Check the NetBox logs:
   ```bash
   docker logs <deployment-name>-netbox-1 --tail 50
   ```
2. Ensure PostgreSQL is healthy:
   ```bash
   docker compose ps postgres
   ```
3. For hosts with less than 2 GiB of available memory, migrations may take 5–10 minutes. Wait for completion.
4. If migrations fail, check for PostgreSQL connection issues in the logs and verify `secrets/db_password` matches `env/postgres.env`.

### Dependent containers stuck in "Created" state

**Symptom**: After NetBox becomes healthy, some containers remain in `Created` state.

**Resolution**: Re-run `docker compose up -d` to trigger the dependency chain.

### Secret file errors

**Symptom**: Containers fail to start with "secret not found" errors.

**Resolution**: Ensure all `.example` files in `secrets/` have been copied to their non-example counterparts:

```bash
cd secrets
ls *.example | while read f; do
  target="${f%.example}"
  [ ! -f "$target" ] && echo "Missing: $target"
done
```

## TLS Issues

### Self-signed certificate warnings

**Symptom**: Browser shows certificate warnings when accessing NetBox.

**Cause**: Expected behavior with self-signed certificates.

**Resolution**: Either accept the warning or switch to Let's Encrypt mode with `--fqdn` and `--acme-email`.

### Let's Encrypt certificate not obtained

**Symptom**: Traefik logs show ACME challenge failures.

**Resolution**:

1. Verify `secrets/cf_dns_api_token` contains a valid Cloudflare API token.
2. Ensure the token has `Zone:DNS:Edit` permission for the FQDN's zone.
3. Verify DNS A/AAAA record points to the deployment host.
4. Check Traefik logs:
   ```bash
   docker logs <deployment-name>-traefik-1 --tail 50
   ```

## Plugin Issues

### Plugin fails to load

**Symptom**: NetBox fails to start with a plugin import error.

**Resolution**:

1. Verify the plugin is compatible with NetBox 4.5.x.
2. Check the plugin's `min_version` and `max_version` declarations.
3. Rebuild the NetBox image:
   ```bash
   docker compose build netbox
   docker compose up -d
   ```

### Config Diff plugin is not present

**Symptom**: You expect `netbox-config-diff` settings in `configuration/plugins.py`, but they are missing from the generated bundle.

**Resolution**: This is expected. `netbox-config-diff==2.14.2` is intentionally disabled by default because it crashes NetBox 4.5.7 with a Strawberry `DuplicatedTypeName` error, so its runtime config is not rendered into `configuration/plugins.py`. Treat the absence of config as confirmation that the compatibility gate is active, not as a broken deployment.

## Diode Issues

### Diode env credential placeholders

**Symptom**: Diode services fail to authenticate with `replace-me` errors.

**Resolution**: Update `env/diode.env` with values matching the corresponding secret files:

| Env variable | Source |
|---|---|
| `REDIS_PASSWORD` | Content of `secrets/diode_redis_password` |
| `POSTGRES_PASSWORD` | Content of `secrets/db_password` |
| `DIODE_TO_NETBOX_CLIENT_SECRET` | Content of `secrets/netbox_to_diode` |

### ORB agent dry-run mode

**Symptom**: ORB agent runs but does not create objects in NetBox.

**Cause**: The generated configuration defaults to `dry_run: true`.

**Resolution**: Edit `configuration/orb/agent.yaml` and set `dry_run: false` after verifying Diode credentials are correct.

## Import Issues

### Device-type library import fails

**Symptom**: The import service exits with an error.

**Resolution**:

1. Ensure NetBox is healthy and the superuser sync has completed.
2. Check the import logs:
   ```bash
   docker compose --profile device-type-library-import logs device-type-library-import
   ```
3. Verify the v2 API token exists in the `token-store` volume.

### Geographic data import fails

**Symptom**: The geo-foss service exits with an error.

**Resolution**:

1. Ensure `netbox-superuser-sync` has completed successfully.
2. Build the geo-foss image first:
   ```bash
   docker compose build netbox-geo-foss
   ```
3. Check if the `token-store` volume contains the v2 token.
4. If using GeoNames API, verify `GEONAMES_USERNAME` in `env/geo-foss.env`.

## WSL-Specific Issues

### Published ports not accessible from Windows

**Symptom**: NetBox is running but not accessible from the Windows browser.

**Resolution**: Pass `--host-ip <windows-lan-ip>` when generating the bundle so published ports, public URLs, and identity redirects use the real host address instead of the guest NAT address.

### Docker volume performance

**Symptom**: Slow database performance or container startup.

**Resolution**: The factory generates a warning about WSL environments. Use persistent Docker volumes (the default) instead of bind mounts for database and application data.

## Monitoring Stack Issues

### Grafana shows no data

**Symptom**: Grafana dashboards are empty after starting the monitoring stack.

**Resolution**:

1. Run the dashboard fetch script first:
   ```bash
   ./scripts/fetch-monitoring-dashboards.sh
   ```
2. Verify Prometheus is scraping targets:
   ```bash
   # Check Prometheus targets page
   docker compose --profile monitoring exec prometheus wget -qO- http://localhost:9090/api/v1/targets | python3 -m json.tool
   ```
3. Wait 1–2 minutes for initial data collection.

## Identity Stack Issues

### Authentik bootstrap fails

**Symptom**: The `authentik-bootstrap-netbox` container exits with errors.

**Resolution**:

1. Ensure Authentik server is healthy.
2. Check that `secrets/authentik_secret_key` and `secrets/authentik_pg_password` are populated.
3. Review the bootstrap container logs:
   ```bash
   docker compose --profile identity logs authentik-bootstrap-netbox
   ```

## Validation Commands

Use these commands to verify the deployment health:

```bash
# Check all service status
docker compose ps

# Check NetBox health
docker compose exec netbox python -c "
from urllib.request import urlopen; import sys
response = urlopen('http://127.0.0.1:8080/login/', timeout=10)
sys.exit(0 if response.status == 200 else 1)
"

# Check PostgreSQL health
docker compose exec postgres pg_isready

# Check Valkey health
docker compose exec valkey valkey-cli ping

# View deployment plan
cat deployment-plan.json | python3 -m json.tool | head -50
```
