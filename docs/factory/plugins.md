# Plugin Catalog

The factory includes 11 plugin specifications with explicit compatibility metadata. Each plugin is either enabled or disabled based on upstream NetBox version compatibility declarations.

## Compatibility Matrix

| Plugin | Package | Version | Enabled | Support Tier | NetBox Compatibility |
|--------|---------|---------|---------|-------------|---------------------|
| Topology Views | `netbox-topology-views` | 4.5.1 | ✅ | supported-community | NetBox 4.5.x |
| BGP | `netbox-bgp` | 0.18.1 | ✅ | supported-community | NetBox 4.5.x |
| DNS | `netbox-plugin-dns` | 1.5.5 | ✅ | supported-community | min_version='4.5.0' |
| ACLs | `netbox-acls` | 2.0.0 | ✅ | supported-community | NetBox 4.5.x |
| Reorder Rack | `netbox-reorder-rack` | 1.1.4 | ✅ | community | >=4.0.0 |
| Prometheus SD | `netbox-prometheus-sd` | 0.5 | ❌ | community-legacy | Legacy API, fails on 4.5.x |
| Diode | `netboxlabs-diode-netbox-plugin` | 1.9.0 | ✅ | supported-netboxlabs | NetBox >= 4.5.0 |
| Proxbox | `netbox-proxbox` | 0.0.10 | ✅ | community | NetBox 4.5.x |
| Config Diff | `netbox-config-diff` | 2.14.2 | ❌ | community | min='4.5.0', max='4.5.99'; DuplicatedTypeName crash on 4.5.7 |
| Floorplan | `netbox-floorplan-plugin` | 0.9.1 | ✅ | community | min='4.5.0-beta1', max='4.5.99' |
| Inventory | `netbox-inventory` | 2.5.1 | ✅ | community | min='4.5.0' |

## Enabled Plugins

### Topology Views

- **Package**: `netbox-topology-views==4.5.1`
- **Module**: `netbox_topology_views`
- **Support Tier**: supported-community

Provides topology visualization as a direct modeling extension. The generated configuration enables coordinate persistence and creates the expected static image directory in the custom image.

**Generated Configuration:**

```python
PLUGINS_CONFIG = {
    "netbox_topology_views": {
        "static_image_directory": "netbox_topology_views/img",
        "allow_coordinates_saving": True,
        "always_save_coordinates": True,
    }
}
```

### BGP

- **Package**: `netbox-bgp==0.18.1`
- **Module**: `netbox_bgp`
- **Support Tier**: supported-community

Extends NetBox as a source of truth for BGP sessions, peer groups, policy, and AS-path artifacts. Exposes BGP data on a device tab and enables a top-level menu.

**Generated Configuration:**

```python
PLUGINS_CONFIG = {
    "netbox_bgp": {
        "device_ext_page": "tab",
        "top_level_menu": True,
    }
}
```

### DNS

- **Package**: `netbox-plugin-dns==1.5.5`
- **Module**: `netbox_dns`
- **Support Tier**: supported-community

Provides DNS zone, record, nameserver, and DNSSEC key template management natively inside NetBox. Explicitly declares `min_version='4.5.0'`.

**Generated Configuration:** Uses package defaults. Operators who require custom SOA timers, zone TTL defaults, or filtered RR types can extend `PLUGINS_CONFIG["netbox_dns"]` in the generated `configuration/plugins.py`.

### Reorder Rack

- **Package**: `netbox-reorder-rack==1.1.4`
- **Module**: `netbox_reorder_rack`
- **Support Tier**: community

Exposes drag-and-drop rack reordering. Upstream compatibility matrix states `>=4.0.0`.

!!! warning "Staging Validation"
    Validate in staging before production because upstream metadata does not publish a strict NetBox 4.5 compatibility matrix.

**Generated Configuration:** Uses package defaults.

### ACLs

- **Package**: `netbox-acls==2.0.0`
- **Module**: `netbox_acls`
- **Support Tier**: supported-community

Official netbox-community plugin. Version 2.0.0 explicitly targets NetBox 4.5.x in the upstream compatibility matrix.

**Generated Configuration:**

```python
PLUGINS_CONFIG = {
    "netbox_acls": {
        "top_level_menu": True,
    }
}
```

### Diode

- **Package**: `netboxlabs-diode-netbox-plugin==1.9.0`
- **Module**: `netbox_diode_plugin`
- **Support Tier**: supported-netboxlabs

Official NetBox Labs Diode plugin providing reconciliation APIs for automated network state ingestion. Upstream compatibility table shows NetBox >= 4.5.0 support.

**Generated Configuration:**

```python
PLUGINS_CONFIG = {
    "netbox_diode_plugin": {
        "diode_username": "diode",
        "diode_target_override": "grpc://diode-auth:8080/diode",
        "secrets_path": "/run/secrets/",
        "netbox_to_diode_client_id": "netbox-to-diode",
        "netbox_to_diode_client_secret_name": "netbox_to_diode",
    }
}
```

The `diode_target_override` points at the generated `diode-auth` Compose service so plugin and reconciler endpoints resolve within the composed deployment.

### Proxbox

- **Package**: `netbox-proxbox==0.0.10`
- **Module**: `netbox_proxbox`
- **Support Tier**: community

Integrates Proxmox VE inventory (clusters, nodes, VMs, containers) with NetBox as the network source of truth. Version 0.0.10 explicitly lists NetBox 4.5.x in its requirements.

**Generated Configuration:** Uses package defaults.

### Floorplan

- **Package**: `netbox-floorplan-plugin==0.9.1`
- **Module**: `netbox_floorplan`
- **Support Tier**: community

Provides visual floorplan management for sites and locations. From [netbox-community/netbox-floorplan-plugin](https://github.com/netbox-community/netbox-floorplan-plugin). Upstream declares `min_version='4.5.0-beta1'` and `max_version='4.5.99'`.

**Generated Configuration:** Uses package defaults.

### Inventory

- **Package**: `netbox-inventory==2.5.1`
- **Module**: `netbox_inventory`
- **Support Tier**: community

Extends NetBox with asset lifecycle tracking, purchase, and warranty management. From [ArnesSI/netbox-inventory](https://github.com/ArnesSI/netbox-inventory). Upstream declares `min_version='4.5.0'`.

**Generated Configuration:** Uses package defaults.

## Disabled Plugins

Disabled plugins are included in the specification list for documentation and future enablement, but are not installed in the generated image.

### Prometheus Service Discovery

- **Package**: `netbox-prometheus-sd==0.5`
- **Module**: `netbox_prometheus_sd`
- **Support Tier**: community-legacy
- **Reason**: Current release imports the legacy `extras.plugins` API and fails to load on NetBox 4.5.x.

Enable once an updated release targets modern NetBox plugin APIs.

### Config Diff

- **Package**: `netbox-config-diff==2.14.2`
- **Module**: `netbox_config_diff`
- **Support Tier**: community
- **Reason**: Version 2.14.2 triggers a `DuplicatedTypeName('StrFilterLookup')` error in the strawberry GraphQL layer on NetBox 4.5.7, preventing the application from starting.

Enable once upstream releases a version that resolves the GraphQL schema conflict.

**Prepared Configuration:** `custom_field_name: "monitored"`, `target_port: 9100`, `gnmic_target_port: 32767`

## Support Tiers

| Tier | Description |
|------|-------------|
| `supported-community` | Official netbox-community plugin with explicit NetBox version compatibility |
| `supported-netboxlabs` | Official NetBox Labs plugin |
| `community` | Community plugin with upstream compatibility metadata |
| `community-legacy` | Community plugin with outdated or broken compatibility |

## Adding a Plugin

To add a new plugin to the factory:

1. Add a `PluginSpec` entry to `DEFAULT_PLUGIN_SPECS` in `constants.py`.
2. Verify upstream compatibility metadata (`min_version`, `max_version`) against the pinned `NETBOX_VERSION`.
3. Set `enabled=True` only if compatibility is confirmed.
4. Document the plugin in this catalog.
5. Update the version pins table in `netbox_deployment_factory/README.md`.
