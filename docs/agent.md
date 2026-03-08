# Agent Specification

This document defines the comprehensive specification for the Ultimate Info Gather agent, serving as a blueprint for future feature development and AI/automation integrations.

## Overview

The Ultimate Info Gather agent is designed to be a foundational component for system automation, monitoring, and AI-assisted operations. This specification outlines the agent's capabilities, interfaces, and extension points.

---

## Agent Identity

| Property | Value |
|----------|-------|
| **Name** | Ultimate Info Gather Agent |
| **Version** | 1.0.0 |
| **Type** | System Information Collection Agent |
| **Runtime** | Python 3.11+ (async) |
| **Platform** | Linux (primary), extensible to other platforms |

---

## Core Capabilities

### 1. Environment Awareness

The agent can determine and report:

- **Execution Context**
  - Running as script, module, subprocess, or interactive
  - Container environment detection (Docker, Kubernetes, LXC)
  - Virtual machine detection and hypervisor identification
  - WSL environment detection
  
- **Python Runtime**
  - Version and implementation details
  - Virtual environment status
  - Package installation paths
  
- **Process Identity**
  - PID, PPID, and process tree position
  - User/group identity (real and effective)
  - Working directory and arguments

### 2. Permission Analysis

The agent can analyze and report:

- **Access Levels**
  - ROOT: Full system access
  - SUDO: Can elevate privileges
  - PRIVILEGED: Member of elevated groups
  - STANDARD: Normal user permissions
  - RESTRICTED: Limited capabilities
  - SANDBOXED: Heavily constrained
  
- **Linux Capabilities**
  - CAP_SYS_ADMIN, CAP_NET_ADMIN, CAP_DAC_OVERRIDE
  - Full capability enumeration
  
- **Security Contexts**
  - SELinux status and context
  - AppArmor status and profile
  
- **Resource Limits**
  - Open files, processes, memory, CPU time
  - All standard ulimits

### 3. Hardware Inventory

The agent can enumerate:

- **Compute Resources**
  - CPU model, cores, frequency, cache, flags
  - Memory total, available, swap
  
- **Storage**
  - Block devices, partitions, mount points
  - Device types (HDD, SSD, NVMe)
  - Access levels and SMART status
  
- **Graphics**
  - GPU enumeration (NVIDIA, AMD, Intel)
  - Driver versions, memory
  
- **Peripherals**
  - USB device enumeration
  - PCI device listing

### 4. Network Capabilities (Intensive In-Depth)

The agent provides comprehensive network analysis:

- **Extended Interface Information**
  - Interface names, MAC addresses, IP addresses (IPv4/IPv6)
  - Interface states (up/down), loopback, virtual
  - Speed, MTU, duplex mode, carrier status
  - Driver information
  - Per-interface statistics (RX/TX bytes, packets, errors, dropped)
  - Broadcast address, netmask, gateway

- **Routing Information**
  - Full routing table (IPv4 and IPv6)
  - Default gateway and interface
  - Route types (default, local, static, dynamic)
  - Route metrics and flags

- **DNS Configuration**
  - Nameservers from /etc/resolv.conf
  - Search domains
  - DNS options

- **ARP Table**
  - IP to MAC address mappings
  - Interface associations
  - Entry states and flags

- **Network Connections**
  - Active TCP/UDP connections
  - Connection states (LISTEN, ESTABLISHED, TIME_WAIT, etc.)
  - Local and remote addresses/ports
  - Process information (PID, process name)

- **Listening Ports**
  - TCP/UDP listening sockets
  - Bound addresses and ports
  - Associated processes
  - Service name mapping

- **Firewall Status**
  - Detection of firewall type (nftables, iptables, ufw, firewalld)
  - Firewall enabled/disabled status
  - Default policies (INPUT, OUTPUT, FORWARD)
  - Rules count and active zones

- **Traffic Summary**
  - Total RX/TX bytes across interfaces
  - Active connection count
  - Listening ports count

### 5. Software Inventory

The agent can catalog:

- **Operating System**
  - Distribution, version, kernel
  - Boot time, uptime
  
- **Package Management**
  - Installed packages (apt, rpm, pacman, etc.)
  - Python packages via pip
  
- **Services**
  - Systemd/init service status
  - Service control capabilities
  
- **Containers**
  - Docker, Podman, containerd
  - Running container enumeration
  
- **Processes**
  - Active process listing
  - Resource usage per process

---

## Agent Interfaces

### Programmatic API

```python
from src.orchestrator import InfoGatherOrchestrator

# Create agent instance
agent = InfoGatherOrchestrator(
    output_dir='./output',
    progress_callback=my_callback,
)

# Execute full collection
report = await agent.collect_all()

# Access stored state
env = agent.environment_state      # EnvironmentState
perms = agent.permissions_info     # PermissionsInfo
hw = agent.hardware_info           # HardwareInfo
net = agent.network_info           # NetworkInfo (intensive in-depth)
sw = agent.software_info           # SoftwareInfo

# Generate outputs
outputs = await agent.generate_outputs(report, ['json', 'markdown'])
```

### Command Line Interface

```bash
# Basic execution (outputs to ./output in json, markdown, text)
python main.py

# Specify output directory
python main.py -o ./reports

# Select output formats
python main.py -f json markdown

# Verbose output
python main.py -v

# Quiet mode (no progress)
python main.py -q
```

| Flag | Long Form | Default | Description |
|------|-----------|---------|-------------|
| `-o` | `--output` | `./output` | Output directory for reports |
| `-f` | `--formats` | `json markdown text` | Output format(s) to generate |
| `-v` | `--verbose` | off | Verbose output with full summary |
| `-q` | `--quiet` | off | Quiet mode, suppresses progress output |

### Output Formats

| Format | Use Case |
|--------|----------|
| JSON | API integration, data processing |
| Markdown | Documentation, human review |
| Text | Console output, logging |

---

## Extension Points

### Custom Collectors

Create new collectors by extending `BaseCollector`:

```python
from src.collectors.base import BaseCollector
from dataclasses import dataclass

@dataclass
class CustomData:
    # Define your data model
    pass

class CustomCollector(BaseCollector[CustomData]):
    async def collect(self) -> CustomData:
        # Implement collection logic
        return CustomData(...)
```

### Custom Output Formats

Add output formats by extending report generation:

```python
def generate_custom_format(report: SystemReport) -> str:
    data = report.to_dict()
    # Transform to custom format
    return custom_output
```

### Plugin Architecture (Future)

```python
# Plugin interface specification
class AgentPlugin:
    """Base class for agent plugins."""
    
    name: str
    version: str
    
    async def on_collection_start(self, agent: InfoGatherOrchestrator) -> None:
        """Called before collection begins."""
        pass
    
    async def on_collection_complete(self, report: SystemReport) -> None:
        """Called after collection completes."""
        pass
    
    async def transform_report(self, report: SystemReport) -> SystemReport:
        """Modify report data."""
        return report
```

---

## Future Development Roadmap

### Phase 1: Core Enhancements

- [ ] **Remote Collection**: SSH-based remote system scanning
- [ ] **Differential Reporting**: Track changes between scans
- [ ] **Real-time Monitoring**: Continuous data collection mode
- [ ] **Windows Support**: Cross-platform capability
- [ ] **macOS Support**: Darwin-specific collectors

### Phase 2: Integration Features

- [ ] **REST API**: HTTP server for remote access
- [ ] **gRPC Service**: High-performance RPC interface
- [ ] **WebSocket Streaming**: Real-time data streaming
- [ ] **Database Storage**: PostgreSQL/SQLite persistence
- [ ] **Prometheus Metrics**: Monitoring system integration
- [x] **NetBox Integration**: Already partially realized via [`netbox_deployment_factory/`](../netbox_deployment_factory/README.md), which consumes the agent's JSON output to generate reproducible NetBox deployment bundles

### Phase 3: Intelligence Features

- [ ] **Anomaly Detection**: ML-based deviation alerts
- [ ] **Security Scanning**: Vulnerability assessment
- [ ] **Compliance Checking**: Policy validation
- [ ] **Recommendation Engine**: Optimization suggestions
- [ ] **Natural Language Queries**: AI-powered data exploration

### Phase 4: Automation

- [ ] **Remediation Actions**: Automated fixes
- [ ] **Scheduled Collection**: Cron-like scheduling
- [ ] **Event Triggers**: Action on condition
- [ ] **Workflow Integration**: CI/CD pipeline support
- [ ] **Multi-Agent Coordination**: Distributed collection

---

## AI/LLM Integration Specification

### Context Provision

The agent provides rich context for AI systems:

```python
# Get full context for AI consumption
context = {
    "environment": agent.environment_state.to_dict(),
    "permissions": agent.permissions_info.to_dict(),
    "hardware": agent.hardware_info.to_dict(),
    "network": agent.network_info.to_dict(),  # Intensive network analysis
    "software": agent.software_info.to_dict(),
}

# Provide to LLM
response = llm.query(
    prompt="Analyze this system and suggest optimizations",
    context=context,
)
```

> **Real-world downstream integration**: The [`netbox_deployment_factory/`](../netbox_deployment_factory/README.md) subproject already consumes this JSON output to generate reproducible NetBox deployment bundles, demonstrating how the agent's structured data can drive infrastructure automation.

### Structured Outputs

All data models support structured serialization:

```python
# JSON Schema for validation
schema = {
    "type": "object",
    "properties": {
        "environment": {"$ref": "#/definitions/EnvironmentState"},
        "permissions": {"$ref": "#/definitions/PermissionsInfo"},
        "network": {"$ref": "#/definitions/NetworkInfo"},
        # ...
    }
}
```

### Query Interface (Future)

```python
# Natural language queries
result = await agent.query("What services are consuming the most memory?")
result = await agent.query("Is Docker properly configured?")
result = await agent.query("What security hardening is missing?")
```

### Action Suggestions (Future)

```python
# Get AI-generated suggestions
suggestions = await agent.get_suggestions()
# [
#     Suggestion(
#         category="security",
#         priority="high",
#         description="SELinux is disabled",
#         action="Enable SELinux enforcing mode",
#         command="sudo setenforce 1",
#     ),
#     ...
# ]
```

---

## Data Schemas

### Report Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SystemReport",
  "type": "object",
  "required": ["report_metadata"],
  "properties": {
    "report_metadata": {
      "type": "object",
      "properties": {
        "report_id": {"type": "string", "format": "uuid"},
        "generated_at": {"type": "string", "format": "date-time"},
        "generator_version": {"type": "string"},
        "total_collection_time_ms": {"type": "number"},
        "collection_errors": {"type": "array", "items": {"type": "string"}},
        "warnings": {"type": "array", "items": {"type": "string"}}
      }
    },
    "environment": {"$ref": "#/definitions/EnvironmentState"},
    "permissions": {"$ref": "#/definitions/PermissionsInfo"},
    "hardware": {"$ref": "#/definitions/HardwareInfo"},
    "network": {"$ref": "#/definitions/NetworkInfo"},
    "software": {"$ref": "#/definitions/SoftwareInfo"}
  }
}
```

---

## Security Considerations

### Data Sensitivity

| Data Type | Sensitivity | Handling |
|-----------|-------------|----------|
| Environment variables | HIGH | Redact secrets |
| Process command lines | MEDIUM | May contain secrets |
| Network addresses | MEDIUM | Internal IPs |
| User information | MEDIUM | PII considerations |
| Hardware serials | LOW | Inventory tracking |

### Redaction Support (Future)

```python
# Configure sensitive data handling
agent = InfoGatherOrchestrator(
    redact_patterns=[
        r'(?i)password[=:]\S+',
        r'(?i)api[_-]?key[=:]\S+',
        r'(?i)secret[=:]\S+',
    ],
    redact_env_vars=['AWS_SECRET_ACCESS_KEY', 'DATABASE_PASSWORD'],
)
```

### Access Control (Future)

```python
# Role-based access
@require_role('admin')
async def collect_sensitive():
    pass

@require_role('viewer')
async def collect_basic():
    pass
```

---

## Performance Specifications

### Collection Timing

| Phase | Typical Duration | Maximum |
|-------|------------------|---------|
| Environment | <100ms | 500ms |
| Permissions | <200ms | 1s |
| Hardware | <500ms | 5s |
| Network | <300ms | 3s |
| Software | <2s | 30s |
| **Total** | <3.5s | 40s |

### Resource Usage

| Resource | Expected | Maximum |
|----------|----------|---------|
| Memory | <100MB | 500MB |
| CPU | <25% | 100% burst |
| Disk I/O | Minimal | Read-only |
| Network | Minimal | Local queries only |

### Concurrency

- Hardware, Network, and Software collectors run in parallel
- Individual collectors use async I/O
- No blocking operations in main thread

---

## Versioning & Compatibility

### Semantic Versioning

- **MAJOR**: Breaking API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

### Schema Versioning

Schema versioning is a **planned future feature** and is not yet implemented. The `schema_version` field does not currently exist in generated reports. Once implemented, it will be included in `report_metadata` for compatibility tracking:

```json
// (Future / Planned — not yet implemented)
{
  "report_metadata": {
    "schema_version": "1.0.0",
    ...
  }
}
```

### Migration Support (Future)

```python
# Upgrade old reports
upgraded = migrate_report(old_report, target_version="2.0.0")
```

---

## Conclusion

This specification serves as the authoritative reference for the Ultimate Info Gather agent. Future development should align with these interfaces and extension points to maintain consistency and compatibility.

For questions or contributions, see the [Contributing Guide](development/contributing.md).
