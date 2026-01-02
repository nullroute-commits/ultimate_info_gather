# Data Models API

## Environment Models

::: src.models.environment.EnvironmentState
    options:
      show_root_heading: true
      members:
        - to_dict
        - get_summary

::: src.models.environment.ExecutionMode
    options:
      show_root_heading: true

::: src.models.environment.PlatformType
    options:
      show_root_heading: true

::: src.models.environment.PythonEnvironment
    options:
      show_root_heading: true

::: src.models.environment.ProcessInfo
    options:
      show_root_heading: true

## Permissions Models

::: src.models.permissions.PermissionsInfo
    options:
      show_root_heading: true
      members:
        - to_dict
        - get_summary

::: src.models.permissions.PermissionLevel
    options:
      show_root_heading: true

::: src.models.permissions.AccessLevel
    options:
      show_root_heading: true

::: src.models.permissions.GroupInfo
    options:
      show_root_heading: true

::: src.models.permissions.FileSystemPermission
    options:
      show_root_heading: true

::: src.models.permissions.ResourceInfo
    options:
      show_root_heading: true

::: src.models.permissions.ResourceLimits
    options:
      show_root_heading: true

## Hardware Models

::: src.models.hardware.HardwareInfo
    options:
      show_root_heading: true
      members:
        - to_dict
        - get_summary

::: src.models.hardware.CPUInfo
    options:
      show_root_heading: true

::: src.models.hardware.MemoryInfo
    options:
      show_root_heading: true

::: src.models.hardware.StorageDevice
    options:
      show_root_heading: true

::: src.models.hardware.NetworkInterface
    options:
      show_root_heading: true

::: src.models.hardware.GPUInfo
    options:
      show_root_heading: true

::: src.models.hardware.USBDevice
    options:
      show_root_heading: true

::: src.models.hardware.DeviceAccessLevel
    options:
      show_root_heading: true

## Software Models

::: src.models.software.SoftwareInfo
    options:
      show_root_heading: true
      members:
        - to_dict
        - get_summary

::: src.models.software.OSInfo
    options:
      show_root_heading: true

::: src.models.software.InstalledPackage
    options:
      show_root_heading: true

::: src.models.software.PythonPackage
    options:
      show_root_heading: true

::: src.models.software.SystemService
    options:
      show_root_heading: true

::: src.models.software.ServiceState
    options:
      show_root_heading: true

::: src.models.software.ContainerInfo
    options:
      show_root_heading: true

::: src.models.software.KernelModule
    options:
      show_root_heading: true

## Report Model

::: src.models.report.SystemReport
    options:
      show_root_heading: true
      members:
        - to_dict
        - to_json
        - save_json
        - get_full_summary
        - get_markdown_report
        - save_markdown
