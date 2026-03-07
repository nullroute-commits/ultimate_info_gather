# Bootstrap Admin Privacy

The deployment bundle intentionally avoids binding the initial superuser to a real person.

## Controls

- The generated username is a pseudonymous `bootstrap-<hash>` alias derived from the source report ID.
- The generated email uses the `.invalid` reserved namespace.
- The compose bundle expects Docker secret files instead of plain-text committed credentials.
- The database password secret is separate from the bootstrap admin password.
- The device-type-library import runs with its own service boundary; by default it reads the username from `superuser_name`, and it can be switched to a dedicated NetBox user via `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE`.
- The bootstrap account is documented as temporary and should be rotated or disabled immediately after first-run configuration.

## Operational Pattern

1. Start NetBox with the pseudonymous bootstrap account.
2. Log in once and create named operator accounts or SSO-backed groups.
3. Grant permissions through RBAC groups instead of sharing the bootstrap user.
4. Rotate the bootstrap password and API token, or disable the account entirely.
5. If the device-type library importer should not use the bootstrap account, point `NETBOX_IMPORT_USERNAME` or `NETBOX_IMPORT_USERNAME_FILE` at a dedicated NetBox user.

## Why This Matches NetBox Labs Practice

NetBox is meant to be an authoritative operational system. That makes change tracking, role separation, and secret hygiene important. A pseudonymous bootstrap admin reduces identity leakage during installation while still allowing the platform to be brought online safely.
