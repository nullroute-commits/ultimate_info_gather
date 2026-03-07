# Collectors API

## Base Collector

::: src.collectors.base.BaseCollector
    options:
      show_root_heading: true
      members:
        - collect
        - safe_collect
        - run_command
        - read_file_async
        - add_error
        - add_warning
        - gather_with_errors

::: src.collectors.base.CollectionResult
    options:
      show_root_heading: true

## Environment Collector

::: src.collectors.environment_collector.EnvironmentCollector
    options:
      show_root_heading: true
      show_source: true
      members:
        - collect

## Permissions Collector

::: src.collectors.permissions_collector.PermissionsCollector
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - collect

## Hardware Collector

::: src.collectors.hardware_collector.HardwareCollector
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - collect

## Network Collector

::: src.collectors.network_collector.NetworkCollector
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - collect

## Software Collector

::: src.collectors.software_collector.SoftwareCollector
    options:
      show_root_heading: true
      show_source: true
      members:
        - __init__
        - collect
