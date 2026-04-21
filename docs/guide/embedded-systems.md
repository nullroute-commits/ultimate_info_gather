# Embedded Systems Support

Ultimate Info Gather has been designed to work effectively on embedded Linux systems like routers, IoT devices, and single-board computers.

## Supported Embedded Platforms

- **OpenWrt** - Router firmware (tested on GL-MT6000)
- **ARM-based systems** - Raspberry Pi, BeagleBone, etc.
- **Embedded routers** - GL.iNet, Ubiquiti, etc.
- **Other embedded Linux** - Any system with Python 3.11+

## Key Differences from Standard Linux

### Missing System Files

Embedded systems often lack certain system files that are present on standard x86_64 Linux systems:

#### DMI/SMBIOS Information
- **Files**: `/sys/class/dmi/id/*`
- **Impact**: Not available on ARM systems
- **Behavior**: Silently skipped, no warnings generated
- **Alternative**: CPU info from `/proc/cpuinfo` is used instead

#### Machine ID
- **File**: `/etc/machine-id`
- **Impact**: Optional on embedded systems
- **Behavior**: Silently skipped if missing
- **Alternative**: System identification uses hostname and other identifiers

### Virtual Network Interfaces

Embedded systems often have many virtual network interfaces (bridges, VPN tunnels, VLANs):

#### Network Speed Reading
- **Issue**: Reading `/sys/class/net/*/speed` returns `EINVAL` for virtual interfaces
- **Affected Interfaces**: `br-lan`, `wgclient`, `tun0`, `veth`, etc.
- **Behavior**: Errors are suppressed, speed remains `null`
- **Impact**: Real physical interfaces still report correct speeds

## Package Manager Support

### OpenWrt (opkg)

Ultimate Info Gather now supports OpenWrt's `opkg` package manager:

```bash
# Example output on OpenWrt
{
  "installed_packages_count": 247,
  "package_managers_available": ["opkg"],
  "installed_packages_sample": [
    {
      "name": "busybox",
      "version": "1.35.0-4",
      "package_manager": "opkg"
    }
  ]
}
```

### Supported Package Managers

1. **opkg** - OpenWrt, embedded systems (checked first)
2. **dpkg** - Debian, Ubuntu
3. **rpm** - RHEL, CentOS, Fedora
4. **pacman** - Arch Linux
5. **apk** - Alpine Linux

## Example: Running on OpenWrt

### Installation

```bash
# Install Python 3.11+ on OpenWrt
opkg update
opkg install python3 python3-pip

# Clone and install
git clone https://github.com/nullroute-commits/ultimate_info_gather.git
cd ultimate_info_gather
python3 main.py
```

### Expected Output

On an OpenWrt GL-MT6000 router:

```json
{
  "environment": {
    "platform_type": "LINUX",
    "hostname": "GL-MT6000",
    "is_root": true,
    "is_container": false
  },
  "hardware": {
    "cpu": {
      "model_name": "ARMv8 Processor rev 4 (v8l)",
      "architecture": "aarch64",
      "physical_cores": 4
    },
    "network_interfaces": [
      {"name": "eth0", "speed_mbps": 2500},
      {"name": "br-lan", "speed_mbps": null},
      {"name": "wgclient1", "speed_mbps": null}
    ]
  },
  "software": {
    "os_info": {
      "name": "OpenWrt",
      "version": "21.02-SNAPSHOT"
    },
    "package_managers_available": ["opkg"]
  }
}
```

### Reduced Warnings

Before improvements:
- ~15 warnings about missing DMI files and network speeds

After improvements:
- 0-1 warnings (only for actual permission issues)

## Performance Considerations

### Memory Usage

Embedded systems often have limited RAM. Ultimate Info Gather is designed to be memory efficient:

- **Typical RAM usage**: 10-50 MB
- **Minimum recommended**: 256 MB RAM
- **Async collection**: Efficient parallel data gathering

### Collection Time

On embedded hardware:
- **Fast devices** (quad-core ARM): 500-1000ms
- **Slower devices** (single-core): 2-5 seconds

### Optimization Tips

1. **Limit output formats**: Use only JSON to reduce processing
   ```bash
   python3 main.py -f json
   ```

2. **Disable verbose mode**: Reduces memory for progress tracking
   ```bash
   python3 main.py -q
   ```

3. **Target specific collections**: Future feature for selective collection

## Troubleshooting

### Python Version

OpenWrt may have older Python versions:

```bash
# Check Python version
python3 --version

# If < 3.11, install from packages or compile
opkg install python3-pip python3-dev
```

### Missing Dependencies

Most dependencies are in Python standard library, but some systems may need:

```bash
# OpenWrt
opkg install python3-asyncio python3-logging

# If building from source is needed
opkg install python3-pip gcc make
```

### Permission Issues

Even as root, some embedded systems have restricted filesystems:

```bash
# Run as root if possible
sudo python3 main.py

# Or with specific capabilities
setcap cap_sys_admin+ep /opt/bin/python3.11
```

## Best Practices

1. **Use verbose mode** initially to understand your system
   ```bash
   python3 main.py -v
   ```

2. **Check warnings** - they indicate missing features
   ```bash
   cat output/report_*.json | jq '.report_metadata.warnings'
   ```

3. **Regular collection** - Monitor system changes over time
   ```bash
   # Cron job for daily collection
   0 0 * * * cd /root/ultimate_info_gather && python3 main.py -q -o /data/reports
   ```

4. **Storage management** - Embedded systems have limited storage
   ```bash
   # Keep only recent reports
   find /data/reports -name "*.json" -mtime +30 -delete
   ```

## Known Limitations

### Embedded-Specific

1. **No USB device details** - Limited access to USB metadata
2. **No GPU information** - Embedded GPUs not well exposed in sysfs
3. **Limited SMART data** - eMMC/flash storage doesn't provide SMART info
4. **Container detection** - May not work on all embedded container runtimes

### Future Enhancements

- [ ] Better SoC (System-on-Chip) detection
- [ ] Wireless interface details (signal strength, channel)
- [ ] Flash/eMMC wear information
- [ ] OpenWrt-specific configuration detection
- [ ] Device tree information parsing

## Contributing

If you use Ultimate Info Gather on embedded systems, please:

1. Report any issues specific to your platform
2. Share example outputs (anonymized)
3. Contribute support for additional package managers
4. Suggest embedded-specific features

See the [contributing guide](../development/contributing.md) for details.
