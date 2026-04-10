"""Generated plugin configuration for NetBox."""

PLUGINS = [   'netbox_topology_views',
    'netbox_bgp',
    'netbox_dns',
    'netbox_acls',
    'netbox_reorder_rack',
    'netbox_diode_plugin',
    'netbox_proxbox',
    # 'netbox_config_diff',  # Disabled: StrFilterLookup DuplicatedTypeName w/ NetBox 4.5.7
    'netbox_floorplan',
    'netbox_inventory']

PLUGINS_CONFIG = {   'netbox_acls': {'top_level_menu': True},
    'netbox_bgp': {'device_ext_page': 'tab', 'top_level_menu': True},
    # 'netbox_config_diff': disabled due to strawberry GraphQL schema conflict
    'netbox_diode_plugin': {   'diode_target_override': 'grpc://diode-auth:8080/diode',
                               'diode_username': 'diode',
                               'netbox_to_diode_client_id': 'netbox-to-diode',
                               'netbox_to_diode_client_secret_name': 'netbox_to_diode',
                               'secrets_path': '/run/secrets/'},
    'netbox_topology_views': {   'allow_coordinates_saving': True,
                                 'always_save_coordinates': True,
                                 'static_image_directory': 'netbox_topology_views/img'}}
