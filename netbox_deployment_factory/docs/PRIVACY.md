# Bootstrap Admin Privacy

The deployment bundle intentionally avoids binding the initial superuser to a real person.

## Controls

- The generated username is a pseudonymous `bootstrap-<hash>` alias derived from the source report ID.
- The generated email uses the `.invalid` reserved namespace.
- The compose bundle expects Docker secret files instead of plain-text committed credentials.
- The database password secret is separate from the bootstrap admin password.
- The superuser-sync service writes the full v2 API token (`nbt_<key>.<plaintext>`) to a `token-store` volume so sidecar services (geo-foss, ORB) can authenticate without direct access to the raw secret file.
- The device-type-library import runs with its own service boundary; by default it reads the username from `superuser_name`, and it can be switched to a dedicated NetBox user via `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE`.
- Diode client credentials (`diode_client_id`, `diode_client_secret`, `diode_redis_password`, `netbox_to_diode`) are generated as separate secret files, isolating Diode authentication from the NetBox bootstrap secrets.
- Identity-profile secrets (`authentik_secret_key`, `authentik_pg_password`, `hydra_pg_password`, `hydra_system_secret`) are separate from the core stack so the identity profile can be enabled independently.
- The `env/diode.env` file contains three `replace-me` credential placeholders (`REDIS_PASSWORD`, `POSTGRES_PASSWORD`, `DIODE_TO_NETBOX_CLIENT_SECRET`) that the operator must replace with values matching the corresponding Docker secret files before first start. The `env/hydra.env` file also contains `replace-me` placeholders, but Hydra compose services override them at runtime from Docker secrets.
- The bootstrap account is documented as temporary and should be rotated or disabled immediately after first-run configuration.

## Operational Pattern

1. Start NetBox with the pseudonymous bootstrap account.
2. Log in once and create named operator accounts or SSO-backed groups.
3. Grant permissions through RBAC groups instead of sharing the bootstrap user.
4. Rotate the bootstrap password and API token, or disable the account entirely.
5. If the device-type library importer should not use the bootstrap account, point `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE` at a dedicated NetBox user.

For adjacent services, prefer a dedicated FOSS identity provider such as Authentik (or Keycloak/ZITADEL when those fit better), keep long-lived credentials in a password service such as Vaultwarden, and publish operator bookmarks or documents through a link/cloud layer such as Linkding and Nextcloud instead of overloading the bootstrap account with those duties.

## Why This Matches NetBox Labs Practice

NetBox is meant to be an authoritative operational system. That makes change tracking, role separation, and secret hygiene important. A pseudonymous bootstrap admin reduces identity leakage during installation while still allowing the platform to be brought online safely.
