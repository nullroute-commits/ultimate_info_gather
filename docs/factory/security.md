# Security & Privacy

The deployment factory implements multiple layers of security: pseudonymous identity, secret isolation, network segmentation, and least-privilege container execution. This page documents all security-related design decisions.

## Privacy Model

The deployment bundle intentionally avoids binding the initial superuser to a real person.

### Pseudonymous Bootstrap Admin

- The generated username is a `bootstrap-<hash>` alias derived from a SHA-256 hash of the source report ID.
- The generated email uses the `.invalid` reserved namespace (e.g. `bootstrap-10f19331c8@invalid.local`).
- The bootstrap account is documented as temporary and should be rotated or disabled immediately after first-run configuration.

### Operational Pattern

1. Start NetBox with the pseudonymous bootstrap account.
2. Log in once and create named operator accounts or SSO-backed groups.
3. Grant permissions through RBAC groups instead of sharing the bootstrap user.
4. Rotate the bootstrap password and API token, or disable the account entirely.
5. If the device-type library importer should not use the bootstrap account, point `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE` at a dedicated NetBox user.

## Secrets Management

All credentials are managed through Docker secret files. No credentials are stored in environment variables, committed to source control, or embedded in container images.

### Secret Files

The generated bundle creates `.example` files in `secrets/` with a `.gitignore` preventing real secrets from being committed:

| Secret File | Purpose |
|-------------|---------|
| `api_token_pepper_1` | NetBox API token pepper for v2 token minting |
| `db_password` | PostgreSQL database password |
| `secret_key` | NetBox secret key |
| `superuser_name` | Bootstrap admin username |
| `superuser_password` | Bootstrap admin password |
| `superuser_api_token` | Bootstrap API token plaintext |
| `diode_redis_password` | Diode Redis/Valkey password |
| `diode_client_id` | Diode OAuth2 client ID |
| `diode_client_secret` | Diode OAuth2 client secret |
| `netbox_to_diode` | NetBox-to-Diode client secret |
| `authentik_secret_key` | Authentik secret key (identity profile) |
| `authentik_pg_password` | Authentik PostgreSQL password (identity profile) |
| `hydra_pg_password` | Hydra PostgreSQL password (identity profile) |
| `hydra_system_secret` | Hydra system secret (identity profile) |
| `cf_dns_api_token` | Cloudflare DNS API token (Let's Encrypt mode only) |

### Secret Separation

Secrets are separated by concern:

- **Core stack**: `api_token_pepper_1`, `db_password`, `secret_key`, `superuser_*`
- **Diode**: `diode_redis_password`, `diode_client_id`, `diode_client_secret`, `netbox_to_diode`
- **Identity**: `authentik_secret_key`, `authentik_pg_password`, `hydra_pg_password`, `hydra_system_secret`
- **TLS**: `cf_dns_api_token`

### Diode Environment Placeholders

The `env/diode.env` file contains three `replace-me` credential placeholders that the operator must replace:

| Env Variable | Matching Secret File |
|---|---|
| `REDIS_PASSWORD` | `secrets/diode_redis_password` |
| `POSTGRES_PASSWORD` | `secrets/db_password` |
| `DIODE_TO_NETBOX_CLIENT_SECRET` | `secrets/netbox_to_diode` |

!!! note "Hydra env placeholders"
    The `env/hydra.env` file also contains `replace-me` placeholders (`DSN` and `SECRETS_SYSTEM`), but Hydra compose services override them at runtime from Docker secrets, so no manual replacement is required.

## API Token Model

The factory uses the NetBox v2 API token format:

1. An `api_token_pepper_1` secret is generated so NetBox can mint v2 tokens.
2. The superuser sync script creates a v2 token from `superuser_api_token` using `Token.validate()` for idempotent re-runs.
3. The full v2 token (`nbt_<key>.<plaintext>`) is written to a shared `token-store` volume.
4. Sidecar services (geo-foss, device-type import) read the assembled token from `token-store` without needing direct secret file access.
5. The device-type importer authenticates with `Authorization: Bearer nbt_<key>.<plaintext>`.

## Least Privilege

### Container Security

- All NetBox application services drop all Linux capabilities via `cap_drop: ["ALL"]`.
- All application containers enable `security_opt: ["no-new-privileges:true"]`.
- Worker containers use `tmpfs` for `/tmp`.
- The device-type library import runs as a separate one-shot workload with dropped capabilities.
- The geo-foss import sidecar runs with dropped capabilities and `no-new-privileges`.

### Network Isolation

- Traefik publishes port 443 (always) and port 80 (Let's Encrypt mode). Diode auth binds to loopback (`127.0.0.1:18080`). The monitoring profile publishes Grafana (port 3000) and Alloy (port 1514).
- All other Docker-networked services communicate only over internal Docker networks.
- Six isolated network segments prevent lateral movement between service tiers.
- Services requiring host-level access (syslog-ng, node-exporter, snmp-exporter, Wazuh, ORB) use `network_mode: host`.
- See [Network Segmentation](networking.md) for the full network topology.

### Device-Type Import Permissions

The importer requires only these NetBox DCIM permissions:

| Permission |
|------------|
| `dcim.add_manufacturer` |
| `dcim.view_manufacturer` |
| `dcim.add_devicetype` |
| `dcim.view_devicetype` |
| `dcim.add_moduletype` |
| `dcim.view_moduletype` |
| `dcim.add_racktype` |
| `dcim.view_racktype` |
| `dcim.add_consoleporttemplate` |
| `dcim.add_consoleserverporttemplate` |
| `dcim.add_powerporttemplate` |
| `dcim.add_poweroutlettemplate` |
| `dcim.add_interfacetemplate` |
| `dcim.add_frontporttemplate` |
| `dcim.add_rearporttemplate` |
| `dcim.add_modulebaytemplate` |
| `dcim.add_devicebaytemplate` |
| `dcim.add_inventoryitemtemplate` |

For stricter RBAC, create a dedicated NetBox user with only these permissions and configure a separate token.

## Published Port Summary

| Port | Service | Protocol | Bind Address | Condition |
|------|---------|----------|--------------|-----------|
| 443 | Traefik | HTTPS | `<host-ip>` | Always |
| 80 | Traefik | HTTP (redirect) | `<host-ip>` | Let's Encrypt mode only |
| 18080 | Diode auth | HTTP | `127.0.0.1` | Always (loopback only) |
| 3000 | Grafana | HTTP | `<host-ip>` | Monitoring profile |
| 1514 | Alloy | TCP (syslog) | `<host-ip>` + `127.0.0.1` | Monitoring profile |

!!! note "Host-networked services"
    Services running with `network_mode: host` (syslog-ng, node-exporter, snmp-exporter, Wazuh agent, ORB agent) expose their native ports directly on the host without Docker port mapping. For example, syslog-ng listens on UDP/514 and TCP/601, node-exporter on TCP/9100, and snmp-exporter on TCP/9116.
