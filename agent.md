---
name: Ultimate Info Gather
description: Repository source of truth for the Ultimate Info Gather system-inspection agent, including verified capabilities, current bugs, validation commands, and delivery roadmap.
color: indigo
emoji: 🧠
vibe: Evidence-first system inspection and roadmap planning for the Ultimate Info Gather project.
---

# Ultimate Info Gather Agent

This file is the canonical agent skill and source of truth for this repository.
It is written in the Agency/GitHub Copilot-compatible `agent.md` format and is
the authoritative reference for implemented capabilities, known gaps, and
delivery priorities.

## Identity

- **Project type**: Async Python 3.11+ Linux system inspection framework
- **Primary entry points**: `main.py`, `src/orchestrator.py`
- **Primary outputs**: JSON, Markdown, and text system reports
- **Published mirror**: `docs/agent.md`

## Critical Rules

- Treat this file as the canonical capability and roadmap source for the repo.
- Keep `docs/agent.md` aligned with this file whenever capabilities or roadmap
  details change.
- State only behavior verified in code or by repository validation runs.
- Update tests and user-facing docs with any production behavior change.

## Repository Map

| Path | Purpose |
|------|---------|
| `src/orchestrator.py` | Main orchestration flow, CLI entry logic, output generation |
| `src/collectors/` | Environment, permissions, hardware, network, and software collectors |
| `src/models/` | Dataclasses and serialization for collected state and reports |
| `tests/` | Pytest coverage for collectors, orchestrator, and regression scenarios |
| `docs/` | MkDocs site and published repository documentation |

## Validated Commands

Run from the repository root after activating `venv`:

```bash
python -m pytest tests/ -o addopts=""
ruff check src/ tests/ main.py
mypy src/
mkdocs build
```

## Verified Implemented Capabilities

### 1. Environment collection

Implemented in `src/collectors/environment_collector.py`:

- Python runtime capture (`version`, implementation, executable, prefix, path)
- Process capture (`pid`, `ppid`, uid/gid, cwd, argv)
- Execution mode classification for virtualenv, container, module,
  interactive, subprocess, and script cases
- Linux/Windows/macOS/BSD platform classification
- Hostname, root detection, container detection, WSL detection
- Shell, terminal, home directory, and temp directory capture

### 2. Permission analysis

Implemented in `src/collectors/permissions_collector.py`:

- Permission level classification (`ROOT`, `SUDO`, `PRIVILEGED`, `STANDARD`,
  `RESTRICTED`, `SANDBOXED`)
- User and group inspection
- Partial Linux capability decoding from `/proc/self/status`
- Filesystem permission checks for critical paths
- SELinux and AppArmor presence/context checks
- Non-interactive sudo probing
- CPU, memory, disk, and ulimit resource snapshotting

### 3. Hardware inventory

Implemented in `src/collectors/hardware_collector.py`:

- System board reads from DMI/sysfs when available
- Machine ID and product UUID reads with embedded-safe fallback behavior
- CPU model, flags, cache, frequency, and virtualization flag capture
- Memory totals and swap statistics from `/proc/meminfo`
- Block device enumeration from `/sys/block`
- Basic interface inventory for hardware summary
- GPU detection via `nvidia-smi`, DRM sysfs, and `lspci`
- USB enumeration via `lsusb`
- Virtual machine detection via CPU flags, `systemd-detect-virt`, and DMI

### 4. Network inventory

Implemented in `src/collectors/network_collector.py`:

- Extended interface details (addresses, MTU, duplex, carrier, driver, stats)
- IPv4 and IPv6 route parsing
- DNS config from `/etc/resolv.conf` and interface DNS via `resolvectl` when
  available
- ARP table parsing
- Connection and listening-port parsing from `/proc/net/*`
- Firewall probing for nftables, iptables, ufw, and firewalld
- Aggregate RX/TX and connection summary metrics

### 5. Software inventory

Implemented in `src/collectors/software_collector.py`:

- OS metadata from `/etc/os-release`, uname, and `/proc/uptime`
- Package discovery for `opkg`, `dpkg`, `rpm`, and `pacman`
- Package-manager availability probing (`opkg`, apt-family, rpm-family,
  pacman, zypper, apk, snap, flatpak)
- Python package listing via `pip list`
- Init system detection (`systemd`, `upstart`, `sysvinit`, `openrc`)
- Service discovery through `systemctl`
- Container discovery through Docker and Podman
- Runtime availability probing for Docker/Podman/containerd/cri-o/lxc/lxd
- Running process snapshot from `/proc`

## Verified Current Bugs and Gaps

The following issues are verified in the current codebase and should be treated
as active backlog items rather than aspirational roadmap items.

| ID | Issue | Evidence | Impact |
|----|-------|----------|--------|
| BUG-01 | ~~`EnvironmentState.to_dict()` omitted `environment_variables`.~~ Resolved: `environment_variables` is now serialized. | `src/models/environment.py` | Serialized JSON now includes the full environment dataset. |
| BUG-02 | ~~`SoftwareInfo.to_dict()` exported only package/service/process samples.~~ Resolved: full `installed_packages`, `system_services`, and `running_processes` lists (plus `environment_variables` and `path_directories`) are now serialized. | `src/models/software.py` | Downstream consumers can reconstruct the full software inventory from saved reports. |
| BUG-03 | `running_processes` data uses placeholder zeros/`None` for CPU, memory, thread count, cwd, and start time. | `src/collectors/software_collector.py` | Process inventory is structurally present but operationally incomplete. |
| BUG-04 | `system_services` data leaves `is_enabled`, `pid`, `user`, `start_time`, `memory_bytes`, and `cpu_percent` unset. | `src/collectors/software_collector.py` | Service inventory is too shallow for operational decisions. |
| BUG-05 | Capability decoding is partial, not full Linux capability enumeration. | `src/collectors/permissions_collector.py` | Permission analysis can miss newer capabilities on modern kernels. |
| BUG-06 | MkDocs build emits duplicate `mkdocs_autorefs` warnings because API docs are generated in two locations. | `mkdocs.yml`, `docs/gen_ref_pages.py`, `docs/api/*.md` | Documentation builds are noisy and link resolution is ambiguous. |
| BUG-07 | The previous `docs/agent.md` overstated implemented behavior relative to the actual collectors. | previous `docs/agent.md` vs `src/collectors/*` | The repository lacked a reliable capability source of truth. |

## Delivery Sprint Plan

### Sprint 1 — Source of truth, docs fidelity, and release hygiene

- Establish `agent.md` as the canonical repository skill and source of truth
- Keep `docs/agent.md` as the published mirror for MkDocs consumers
- Align README and tooling docs with the new source-of-truth workflow
- Remove overstated claims from agent/spec documentation
- Define a stable bug/backlog taxonomy for validated gaps

### Sprint 2 — Report serialization correctness

- Serialize the full environment payload, including environment variables
- Decide and document whether software reports should emit full lists or
  clearly versioned summary payloads
- Add explicit tests for serialization completeness and backward compatibility
- Version the JSON report contract to protect downstream integrations

### Sprint 3 — Software inventory operational depth

- Replace placeholder process telemetry with real CPU, memory, thread, cwd, and
  start-time data
- Enrich service records with enabled state, pid/user ownership, and resource
  metadata where available
- Extend container records with creation time, networks, and volume details
- Add regression tests for Linux environments with restricted permissions

### Sprint 4 — Permission and platform accuracy

- Expand Linux capability decoding to the current kernel capability set
- Tighten permission-level classification for containerized and sandboxed cases
- Improve cross-distro package/service/runtime detection behavior
- Validate embedded/OpenWrt, mainstream Linux, container, and VM coverage

### Sprint 5 — Documentation system cleanup

- Eliminate duplicate MkDocs reference generation so builds are warning-free
- Keep API reference ownership clear between handwritten guides and generated
  reference pages
- Add a docs validation gate that fails on broken internal links or unresolved
  references
- Publish a contributor workflow that treats docs drift as a release blocker

### Sprint 6 — Deliverable completeness

- Define the minimum “production-deliverable” report quality bar for each
  collection domain
- Add smoke-test fixtures or golden reports for representative target
  environments
- Package release artifacts and example outputs for operators and integrators
- Cut a documented release once report fidelity, docs, and validation are all
  green

## Success Criteria

The project is operationally complete when:

- Saved reports faithfully represent the collected runtime data
- Collector outputs are verified across the target Linux environments
- Docs build cleanly without autorefs ambiguity
- `agent.md`, `docs/agent.md`, README, and tests agree on what is actually
  implemented
- A user can install, run, validate, and consume the tool without relying on
  unstated behavior
