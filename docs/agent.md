# Agent Specification

This page is the published mirror of the repository-root
[`agent.md`](../agent.md). The root file is the canonical source of truth for
implemented capabilities, known bugs, and delivery priorities.

## Identity

| Property | Value |
|----------|-------|
| **Name** | Ultimate Info Gather |
| **Type** | Async Python system inspection framework |
| **Runtime** | Python 3.11+ |
| **Primary target** | Linux |
| **Canonical skill / SoT** | `/agent.md` |
| **Published mirror** | `docs/agent.md` |

## Repository Map

| Path | Purpose |
|------|---------|
| `src/orchestrator.py` | Collection sequencing, CLI behavior, output generation |
| `src/collectors/` | Domain collectors for environment, permissions, hardware, network, software |
| `src/models/` | Dataclasses and serializers for collected state and reports |
| `tests/` | Regression and behavior coverage |
| `docs/` | MkDocs site |

## Validated Commands

```bash
python -m pytest tests/ -o addopts=""
ruff check src/ tests/ main.py
mypy src/
mkdocs build
```

## Verified Implemented Capabilities

### 1. Environment collection

Implemented in `src/collectors/environment_collector.py`:

- Python runtime capture
- Process identity capture
- Execution mode classification
- Platform classification
- Hostname, root, container, and WSL detection
- Shell, terminal, home directory, and temp directory capture

### 2. Permission analysis

Implemented in `src/collectors/permissions_collector.py`:

- Permission-level classification
- User and group inspection
- Full Linux capability decoding across the kernel-supported range
- Filesystem permission checks on critical paths
- SELinux and AppArmor presence/context checks
- Non-interactive sudo probing
- Resource and ulimit snapshotting

### 3. Hardware inventory

Implemented in `src/collectors/hardware_collector.py`:

- DMI/system-board reads when available
- Machine ID and product UUID reads with embedded-safe fallback
- CPU, memory, storage, GPU, USB, and basic interface inventory
- Virtual machine detection via CPU flags, `systemd-detect-virt`, and DMI

### 4. Network inventory

Implemented in `src/collectors/network_collector.py`:

- Extended interface inventory with statistics
- IPv4 and IPv6 route parsing
- DNS and ARP collection
- Connection and listening-port parsing
- Firewall probing
- Aggregate RX/TX and connection summaries

### 5. Software inventory

Implemented in `src/collectors/software_collector.py`:

- OS metadata collection
- Package discovery for `opkg`, `dpkg`, `rpm`, and `pacman`
- Python package listing via `pip`
- Init system detection
- Service discovery via `systemctl`, enriched via `systemctl show`
- Container discovery via Docker and Podman
- Running process snapshot from `/proc` with full per-process telemetry

## Verified Current Bugs and Gaps

| ID | Issue | Impact |
|----|-------|--------|
| BUG-01 | ~~Environment variables are collected in memory but omitted from serialized environment output.~~ Resolved: `environment_variables` is serialized. | Saved JSON includes the full environment dataset. |
| BUG-02 | ~~Software serialization exports samples instead of full package/service/process inventories.~~ Resolved: full inventories are serialized. | Downstream integrations can rely on saved reports for full software state. |
| BUG-03 | ~~Process records keep placeholder resource values (`cpu_percent`, `memory_*`, thread count, cwd, start time).~~ Resolved: telemetry is read from `/proc`. | Process inventory carries real, actionable telemetry. |
| BUG-04 | ~~Service records leave several fields unset (`is_enabled`, pid/user, resource usage).~~ Resolved: services are enriched via `systemctl show`. | Service inventory is complete. |
| BUG-05 | ~~Capability decoding is partial rather than full Linux capability coverage.~~ Resolved: capabilities are decoded across the full kernel range. | Permission analysis covers the running kernel's capability set. |
| BUG-06 | MkDocs builds emit duplicate `mkdocs_autorefs` warnings from overlapping reference generation. | Docs builds are noisy and ambiguous. |
| BUG-07 | The prior spec overstated implementation details. | The repo lacked a dependable capability source of truth. |

## Delivery Sprint Plan

### Sprint 1 — Source-of-truth and docs fidelity

- [x] Add repository-root `agent.md` in Agency/GitHub Copilot-compatible format
- [x] Re-align this published spec with the verified implementation
- [x] Document current verified bugs and priorities
- [ ] Keep future capability changes synced between `/agent.md`, this page, README, and tests

### Sprint 2 — Report serialization correctness

- [ ] Serialize environment variables or explicitly version a summary-only contract
- [ ] Decide whether software reports should expose full inventories or versioned summaries
- [ ] Add report-contract regression tests

### Sprint 3 — Software inventory depth

- [x] Replace placeholder process telemetry with real metrics
- [x] Enrich service records with enabled state, pid/user, and resource details
- [ ] Expand container metadata coverage

### Sprint 4 — Permission and platform accuracy

- [x] Expand Linux capability decoding
- [ ] Tighten permission classification across sandbox/container scenarios
- [ ] Validate behavior across mainstream Linux, embedded, container, and VM targets

### Sprint 5 — Documentation system cleanup

- [ ] Remove duplicate MkDocs reference generation
- [ ] Add stricter docs validation for warnings and broken links
- [ ] Keep documentation drift treated as a release blocker

### Sprint 6 — Deliverable readiness

- [ ] Define a minimum production-quality bar for each collector domain
- [ ] Add representative golden reports or smoke-test fixtures
- [ ] Publish release-ready artifacts and example outputs

## Interfaces

### Programmatic API

```python
from src.orchestrator import InfoGatherOrchestrator

orchestrator = InfoGatherOrchestrator(output_dir="./output")
report = await orchestrator.collect_all()
outputs = await orchestrator.generate_outputs(report, ["json", "markdown"])
```

### Command Line Interface

```bash
python3 main.py
python3 main.py -o ./reports
python3 main.py -f json markdown
python3 main.py -v
python3 main.py -q
```

| Flag | Long Form | Default | Description |
|------|-----------|---------|-------------|
| `-o` | `--output` | `./output` | Output directory for reports |
| `-f` | `--format` | `json markdown text` | Output format(s) to generate |
| `-v` | `--verbose` | off | Print the full text summary |
| `-q` | `--quiet` | off | Suppress progress callback output |

### Output Formats

| Format | Use Case |
|--------|----------|
| JSON | Programmatic consumption and integrations |
| Markdown | Human-readable report sharing |
| Text | Console/log output |

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

- Environment and Permissions collectors run sequentially (data dependency)
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
