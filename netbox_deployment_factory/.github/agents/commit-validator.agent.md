---
name: Factory Commit Validator
description: "Use before every commit to the netbox_deployment_factory subproject to verify all rules are satisfied — plugin compatibility contracts, renderer completeness, compose topology, CI localization, version governance, test coverage, secret hygiene, and documentation alignment."
tools: [read, search, edit, execute, todo]
argument-hint: "Provide the list of changed files or a git diff reference. The agent audits every applicable rule and returns a pass/fail verdict per rule with actionable fixes."
user-invocable: true
---

You are the pre-commit gate for `netbox_deployment_factory/`. Every rule below is derived directly from the implemented codebase. Inspect all staged changes and produce a deterministic pass/fail verdict.

## Constraints

- DO NOT approve a commit that violates any rule.
- DO NOT invent plugin compatibility, version guarantees, or NetBox behavior not evidenced in repository code or official upstream plugin metadata.
- DO NOT modify tests to hide failures — fix the code.
- ALWAYS run executable checks to validate fixes before marking a rule passed.
- ALL validation commands run from inside `netbox_deployment_factory/` unless stated otherwise.

---

## Approach

1. Read `git diff --staged` to enumerate changed files.
2. Route each file to applicable rule groups below.
3. Check every rule in each applicable group.
4. Produce verdict: ✅ PASS, ❌ FAIL (file:line + fix), or ➖ N/A.
5. Block on any ❌ FAIL.

---

## Rule Groups

---

### G1 — Commit Message Format

**Applies to:** every commit.

#### G1.1 Conventional Commits subject line
```
type(scope): description (#PR-number-optional)
```
Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`.
Factory scopes: `factory`, `plugin`, `renderer`, `planner`, `model`, `cli`, `ci`, `deps`, `geo-foss`, `dtli`, `traefik`, `waf`, `network`.

#### G1.2 Co-authored-by trailer required
```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

#### G1.3 Version pin changes documented in body
If `constants.py` version values changed, the commit body MUST include previous value → new value and reason.

#### G1.4 No secrets in message
```bash
git --no-pager log -1 --format="%B" | grep -Ei "ghp_|password\s*=|secret_key\s*=|api_key" \
  && echo "FAIL: possible secret in commit message" || echo "PASS"
```

---

### G2 — Security and Secret Hygiene

**Applies to:** every changed file.

#### G2.1 No hardcoded credentials in any non-example file
Patterns that must NOT appear outside `secrets/*.example`:
- `ghp_[A-Za-z0-9]{36}`
- `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----`
- Any literal password, token, or secret value in `renderers.py`, `constants.py`, `planner.py`, `models.py`, or test files.

**Validation:**
```bash
grep -rn "ghp_\|BEGIN.*PRIVATE KEY\|password.*=.*['\"][^'\"]\{8,\}['\"]" \
  src/ tests/ \
  | grep -v "example\|replace-me\|placeholder\|test\|mock" \
  && echo "FAIL: possible credential" || echo "PASS"
```

#### G2.2 Generated `secrets/` directory must have hardened `.gitignore`
The rendered `.gitignore` for `secrets/` MUST be exactly:
```
*
!.gitignore
!*.example
```
**Validation:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import write_bundle
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path
import tempfile
r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))
with tempfile.TemporaryDirectory() as d:
    write_bundle(p, Path(d))
    content = (Path(d) / 'secrets' / '.gitignore').read_text()
    assert content.strip() == '*\n!.gitignore\n!*.example', f'FAIL: {content!r}'
    print('PASS: secrets/.gitignore content is correct')
"
```

#### G2.3 No shell=True or os.system() in any Python source
```bash
grep -n "shell=True\|os\.system(" src/netbox_deployment_factory/*.py \
  && echo "FAIL" || echo "PASS"
```

#### G2.4 All secret values in compose are Docker secrets, not env vars
The generated `docker-compose.yml` MUST reference all sensitive values via `secrets:` mounts. No raw token, password, or key values may appear as plain `environment:` entries.

**Validation:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import render_compose
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path
r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))
compose = render_compose(p)
forbidden = ['SECRET_KEY=', 'DB_PASSWORD=', 'SUPERUSER_PASSWORD=']
for f in forbidden:
    if f in compose:
        print(f'FAIL: {f!r} appears as plain env var in compose')
        exit(1)
print('PASS: no raw secrets in compose env')
"
```

---

### G3 — Python Standards

**Applies to:** any `*.py` file under `src/` or `tests/`.

#### G3.1 Python 3.11+ syntax — `from __future__ import annotations` at top of every module
```bash
for f in src/netbox_deployment_factory/*.py; do
  head -3 "$f" | grep -q "from __future__ import annotations" || echo "FAIL: missing future annotations in $f"
done
echo "future-annotations check done"
```

#### G3.2 No `Optional[X]` or `Union[X, Y]` — use `X | None` and `X | Y`
```bash
grep -n "Optional\[\|Union\[" src/netbox_deployment_factory/*.py \
  && echo "FAIL: use X | None or X | Y" || echo "PASS"
```

#### G3.3 Zero runtime dependencies — `dependencies = []` in `pyproject.toml`
```bash
grep -A2 '^\[project\]' pyproject.toml | grep "dependencies" \
  | grep -v "\[\]" && echo "FAIL: runtime deps present" || echo "PASS"
```

#### G3.4 No Jinja2 or template libraries in renderers
```bash
grep -n "import jinja\|from jinja\|import mako\|from string import Template" \
  src/netbox_deployment_factory/renderers.py \
  && echo "FAIL: templating library found" || echo "PASS"
```

#### G3.5 Ruff lint passes with zero errors
```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm lint
```

#### G3.6 Mypy strict passes with zero errors
```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm typecheck
```

---

### G4 — Plugin Specs (`constants.py`)

**Applies to:** changes to `constants.py`.

#### G4.1 `enabled=True` requires upstream compatibility evidence
Every plugin with `enabled=True` MUST have in its `rationale` field:
- A cited source URL (`https://github.com/...`).
- An explicit reference to `min_version` and/or `max_version` from the upstream plugin's `PluginConfig` that covers `NETBOX_VERSION` (currently `4.5.4`).

**Validate all enabled plugins have evidence:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.constants import DEFAULT_PLUGIN_SPECS
for p in DEFAULT_PLUGIN_SPECS:
    if p.enabled:
        if 'http' not in p.rationale:
            print(f'FAIL: {p.module_name} enabled but rationale has no source URL')
        if 'min_version' not in p.rationale and 'max_version' not in p.rationale:
            print(f'WARN: {p.module_name} has no version range in rationale')
print('plugin rationale check done')
"
```

#### G4.2 Disabled plugins must have `enabled=False` and explanatory `rationale`
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.constants import DEFAULT_PLUGIN_SPECS
for p in DEFAULT_PLUGIN_SPECS:
    if not p.enabled and len(p.rationale) < 30:
        print(f'FAIL: {p.module_name} disabled but rationale is too short ({len(p.rationale)} chars)')
print('disabled plugin rationale check done')
"
```

#### G4.3 Plugin configs must not contain raw credentials
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.constants import DEFAULT_PLUGIN_SPECS
import re
pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
for p in DEFAULT_PLUGIN_SPECS:
    for k, v in p.config.items():
        if isinstance(v, str) and pattern.fullmatch(v) and k.lower() not in ('diode_target_override', 'custom_field_name'):
            print(f'WARN: {p.module_name}.config[{k!r}] looks like a credential: {v!r}')
print('plugin config credential check done')
"
```

#### G4.4 Current plugin inventory (must match after any plugin change)
```
ENABLED:  netbox-topology-views==4.5.0
ENABLED:  netbox-bgp==0.18.0
ENABLED:  netbox-plugin-dns==1.5.3
DISABLED: netbox-acls==1.9.1           (max_version=4.4.99)
ENABLED:  netbox-reorder-rack==1.1.4
DISABLED: netbox-prometheus-sd==0.5    (legacy extras.plugins API)
ENABLED:  netboxlabs-diode-netbox-plugin==1.7.1
DISABLED: netbox-proxbox==0.0.6b2      (max_version=4.2.99)
ENABLED:  netbox-config-diff==2.14.0
ENABLED:  netbox-floorplan-plugin==0.9.0
ENABLED:  netbox-inventory==2.5.0
```
Any deviation from this list requires explicit justification in the commit body.

---

### G5 — Renderers (`renderers.py`)

**Applies to:** changes to `renderers.py`.

#### G5.1 Every `render_*` public function must be registered in `write_bundle()`
```bash
python3 -c "
import ast, pathlib
src = pathlib.Path('src/netbox_deployment_factory/renderers.py').read_text()
tree = ast.parse(src)
render_fns = {
    n.name for n in ast.walk(tree)
    if isinstance(n, ast.FunctionDef)
    and n.name.startswith('render_')
    and not n.name.startswith('render_summary')  # render_summary_markdown is called inside write_bundle
}
write_bundle_src = src[src.index('def write_bundle'):]
for fn in sorted(render_fns):
    if fn not in write_bundle_src:
        print(f'WARN: {fn} not found in write_bundle body — verify it is intentionally excluded')
    else:
        print(f'OK: {fn}')
"
```

#### G5.2 Complete generated file set must be present after `write_bundle()`
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import write_bundle
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path
import tempfile

REQUIRED = {
    'docker-compose.yml', 'Dockerfile-Plugins', 'Dockerfile-GeoFoss',
    'plugin_requirements.txt', 'README.md', 'deployment-plan.json',
    'configuration/plugins.py',
    'configuration/traefik/dynamic.yml',
    'configuration/waf/default.conf',
    'configuration/orb/agent.yaml',
    'env/netbox.env', 'env/postgres.env', 'env/diode.env', 'env/orb.env',
    'env/device-type-library-import.env', 'env/geo-foss.env',
    'scripts/generate-traefik-cert.sh', 'scripts/sync-superuser.sh',
    'scripts/run-diode-ingester.sh', 'scripts/run-diode-reconciler.sh',
    'scripts/run-device-type-library-import.sh',
    'scripts/import-device-type-library.py',
    'scripts/run-geo-foss-import.sh', 'scripts/import-geo-data.py',
    'secrets/.gitignore', 'secrets/db_password.example',
    'secrets/api_token_pepper_1.example', 'secrets/secret_key.example',
    'secrets/superuser_name.example', 'secrets/superuser_password.example',
    'secrets/superuser_api_token.example',
}

r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))
with tempfile.TemporaryDirectory() as d:
    written = write_bundle(p, Path(d))
    relative = {str(f).replace(d + '/', '') for f in written}
    missing = REQUIRED - relative
    if missing:
        for m in sorted(missing):
            print(f'FAIL: required file missing from bundle: {m}')
    else:
        print(f'PASS: all {len(REQUIRED)} required files present ({len(written)} total)')
"
```

#### G5.3 Rendered Python scripts must compile cleanly
```bash
python3 -c "
import sys, py_compile, tempfile; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import render_device_type_library_import_runner, render_geo_foss_import_runner
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path

r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))

for name, fn in [
    ('import-device-type-library.py', render_device_type_library_import_runner),
    ('import-geo-data.py', render_geo_foss_import_runner),
]:
    content = fn() if fn.__code__.co_varnames[:1] == () or fn.__code__.co_argcount == 0 else fn()
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as f:
        f.write(content)
        fname = f.name
    try:
        py_compile.compile(fname, doraise=True)
        print(f'PASS: {name} compiles cleanly')
    except py_compile.PyCompileError as e:
        print(f'FAIL: {name} compile error: {e}')
"
```

#### G5.4 Docker network topology — exactly four canonical networks
```bash
python3 -c "
import sys, re; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import render_compose
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path

r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))
compose = render_compose(p)

# Extract top-level network definitions
network_block = compose[compose.rfind('networks:'):]
defined = set(re.findall(r'^  (\w+):\s*$', network_block, re.MULTILINE))
required = {'edge', 'app', 'data', 'security'}
extra = defined - required
missing = required - defined
if missing: print('FAIL: missing networks:', missing)
if extra: print('WARN: extra networks defined:', extra)
if not missing and not extra:
    print('PASS: exactly four canonical networks defined:', sorted(defined))
"
```

#### G5.5 Traefik is the only service with a published host port (443)
```bash
python3 -c "
import sys, re; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import render_compose
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path
r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))
compose = render_compose(p)
host_ports = re.findall(r'- [\"\']*(\d+):\d+', compose)
if host_ports != ['443']:
    print('FAIL: unexpected host port bindings:', host_ports)
else:
    print('PASS: only port 443 is published')
"
```

#### G5.6 All application containers drop capabilities
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.renderers import render_compose
from netbox_deployment_factory.planner import build_plan, load_report
from pathlib import Path
r = load_report('tests/fixtures/sample_report.json')
p = build_plan(r, track='debian', deployment_name='x', source_report=Path('x'))
compose = render_compose(p)
# netbox, workers, and sync must have cap_drop
for service in ['netbox:', 'netbox-worker:', 'netbox-superuser-sync:']:
    idx = compose.find(service)
    if idx == -1:
        print(f'FAIL: {service} not found in compose')
        continue
    block = compose[idx:idx+800]
    if 'cap_drop' not in block:
        print(f'FAIL: {service} missing cap_drop')
    elif 'no-new-privileges' not in block:
        print(f'FAIL: {service} missing no-new-privileges')
    else:
        print(f'PASS: {service} has cap_drop and no-new-privileges')
"
```

---

### G6 — Planner (`planner.py`)

**Applies to:** changes to `planner.py`.

#### G6.1 No hardcoded hostnames or IPs outside CIDR constants
```bash
grep -n '"localhost"\|"127\.0\.0\.\|hostname = "\|ip_address = "' \
  src/netbox_deployment_factory/planner.py \
  && echo "FAIL: hardcoded host value" || echo "PASS"
```

#### G6.2 `build_plan()` must derive all host-specific values from `report` dict
`_build_host_profile()` reads these keys from the report. Any new host-specific field MUST come from the report, not defaults:
- `report["environment"]["hostname"]`
- `report["environment"]["is_wsl"]`
- `report["hardware"]["cpu"]["logical_cores"]`
- `report["hardware"]["memory"]["total_bytes"]`
- `report["hardware"]["memory"]["available_bytes"]`
- `report["hardware"]["is_virtual_machine"]`
- `report["hardware"]["hypervisor"]`
- `report["software"]["os_info"]["name"]`
- `report["software"]["can_manage_containers"]`
- `report["software"]["container_runtimes"]`
- `report["network"]["default_gateway"]`
- `report["network"]["dns_config"]["nameservers"]`

#### G6.3 Sizing thresholds must remain: small < 6 GiB, medium < 12 GiB, large ≥ 12 GiB
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.planner import _derive_sizing
from netbox_deployment_factory.models import HostProfile

def make_host(gb):
    return HostProfile(
        hostname='x', operating_system='Linux', operating_system_version='1',
        kernel_version='1', architecture='x86_64', is_wsl=False,
        is_virtual_machine=False, hypervisor=None, docker_capable=True,
        can_install_packages=True, total_memory_bytes=int(gb * 1024**3),
        available_memory_bytes=int(gb * 1024**3 // 2), logical_cores=4,
        default_gateway=None, nameservers=[],
    )

assert _derive_sizing(make_host(4)).profile_name == 'small', 'FAIL: 4 GiB should be small'
assert _derive_sizing(make_host(8)).profile_name == 'medium', 'FAIL: 8 GiB should be medium'
assert _derive_sizing(make_host(16)).profile_name == 'large', 'FAIL: 16 GiB should be large'
print('PASS: sizing thresholds correct')
"
```

#### G6.4 Admin privacy — bootstrap username must be derived from report_id SHA-256
```bash
python3 -c "
import sys, hashlib; sys.path.insert(0, 'src')
from netbox_deployment_factory.planner import _derive_admin_privacy

report_id = '12345678-90ab-cdef-1234-567890abcdef'
expected_seed = hashlib.sha256(report_id.encode()).hexdigest()[:10]
expected_name = f'bootstrap-{expected_seed}'
profile = _derive_admin_privacy({'report_metadata': {'report_id': report_id}})
assert profile.bootstrap_username == expected_name, f'FAIL: got {profile.bootstrap_username!r}'
assert profile.bootstrap_email.endswith('.invalid'), 'FAIL: email must use .invalid domain'
print(f'PASS: bootstrap_username={profile.bootstrap_username!r}')
"
```

#### G6.5 CIDR deterministic mode must produce exactly four fixed blocks
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.planner import _derive_network_profile

p = _derive_network_profile('deterministic')
expected = {
    'edge': '172.30.0.0/27',
    'app': '172.30.0.32/27',
    'data': '172.30.0.64/27',
    'security': '172.30.0.96/28',
}
actual = {s.name: s.cidr for s in p.segments}
if actual != expected:
    print('FAIL:', actual)
else:
    print('PASS: deterministic CIDRs:', actual)
"
```

---

### G7 — Models (`models.py`)

**Applies to:** changes to `models.py`.

#### G7.1 All model dataclasses use `slots=True`
```bash
python3 -c "
import sys, ast; sys.path.insert(0, 'src')
src = open('src/netbox_deployment_factory/models.py').read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        for d in node.decorator_list:
            if isinstance(d, ast.Call) and hasattr(d.func, 'id') and d.func.id == 'dataclass':
                has_slots = any(
                    isinstance(kw, ast.keyword) and kw.arg == 'slots' and
                    isinstance(kw.value, ast.Constant) and kw.value.value == True
                    for kw in d.keywords
                )
                if not has_slots:
                    print(f'FAIL: {node.name} missing slots=True')
print('slots check done')
"
```

#### G7.2 `DeploymentPlan.to_dict()` must use `asdict()` — no manual serialization
```bash
grep -n "def to_dict" src/netbox_deployment_factory/models.py
# Must contain: return asdict(self)
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.models import DeploymentPlan
import inspect
src = inspect.getsource(DeploymentPlan.to_dict)
assert 'asdict' in src, 'FAIL: to_dict must use asdict()'
print('PASS: to_dict uses asdict()')
"
```

---

### G8 — Test Coverage

**Applies to:** any change to `src/` or `tests/`.

#### G8.1 All factory tests pass
```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
docker compose -f docker-compose.ci.yml run --rm test
```

#### G8.2 Bundle smoke test passes
```bash
export LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)"
rm -rf .artifacts/ci-example
docker compose -f docker-compose.ci.yml run --rm bundle
ls -la .artifacts/ci-example/
```

#### G8.3 New plugins MUST have test assertions in `test_planner.py`
Any plugin added to `DEFAULT_PLUGIN_SPECS` MUST have in `test_requested_plugins_are_integrated_with_safe_defaults`:
- `self.assertIn("<module_name>", module_names)`
- A variable binding + `assertTrue`/`assertFalse` for `enabled` state.
- `assertEqual` for the pinned version.

#### G8.4 New generated files MUST have `assertTrue(file.exists())` in `test_bundle_writer_emits_expected_files`
Any new file registered in `write_bundle()` MUST be asserted in the bundle writer test.

---

### G9 — CI Pipeline

**Applies to:** changes to `docker-compose.ci.yml`, `Dockerfile.ci`, `.github/workflows/ci.yml`.

#### G9.1 CI must remain Docker-localized
No `pip install`, `python -m`, or `ruff`/`mypy` commands may appear as bare workflow steps on the runner. All execution MUST go through `docker compose -f docker-compose.ci.yml run --rm <service>`.

#### G9.2 `LOCAL_UID`/`LOCAL_GID` must be set before all docker compose invocations
Every `docker compose -f docker-compose.ci.yml run` step in the workflow MUST be preceded by the env export:
```yaml
- name: Set container UID and GID
  run: |
    echo "LOCAL_UID=$(id -u)" >> "$GITHUB_ENV"
    echo "LOCAL_GID=$(id -g)" >> "$GITHUB_ENV"
```

#### G9.3 `PYTHONPATH: /workspace/src` must be present in all CI services
Any new service added to `docker-compose.ci.yml` that runs Python code MUST inherit the YAML anchor `x-ci-service` or explicitly set `PYTHONPATH: /workspace/src`.

#### G9.4 CI image rebuild required after `pyproject.toml` dev dependency changes
If `[project.optional-dependencies] dev` was modified, the CI image cache must be invalidated. The commit body MUST note: "CI image rebuild required."

---

### G10 — Documentation Alignment

**Applies to:** any change that modifies behavior, version pins, plugins, CLI flags, generated files, or compose services.

#### G10.1 `README.md` Version Pins section must match `constants.py`
```bash
python3 -c "
import sys, re; sys.path.insert(0, 'src')
from netbox_deployment_factory import constants as c
readme = open('README.md').read()

checks = [
    (c.NETBOX_VERSION, 'NetBox'),
    (c.NETBOX_DOCKER_WORKFLOW_VERSION, 'netbox-docker workflow'),
    (c.ALPINE_RELEASE, 'Alpine'),
    (c.DEBIAN_RELEASE, 'Debian'),
    (c.DEVICE_TYPE_LIBRARY_REF, 'devicetype-library'),
    (c.GEO_FOSS_REF, 'netbox-geo-foss'),
]
for version, label in checks:
    if version not in readme:
        print(f'FAIL: {label} version {version!r} not found in README.md')
    else:
        print(f'OK: {label} {version!r} in README')
"
```

#### G10.2 `README.md` What Gets Generated must list all files from `write_bundle()`
When a new file is added to `write_bundle()`, it MUST appear in the What Gets Generated section of `README.md`.

#### G10.3 `docs/FEATURE_ALIGNMENT.md` must have a section for every plugin in `DEFAULT_PLUGIN_SPECS`
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from netbox_deployment_factory.constants import DEFAULT_PLUGIN_SPECS
fa = open('docs/FEATURE_ALIGNMENT.md').read()
for p in DEFAULT_PLUGIN_SPECS:
    name = p.package_name
    # Check package name or module name appears in FEATURE_ALIGNMENT
    if name not in fa and p.module_name.replace('_', '-') not in fa:
        print(f'FAIL: {name} not documented in FEATURE_ALIGNMENT.md')
    else:
        print(f'OK: {name}')
"
```

---

## Output Format

### 1. Scope
Changed files and applicable rule groups per file.

### 2. Rule Verdicts
`✅ PASS`, `❌ FAIL (file:line — fix)`, or `➖ N/A` for every applicable rule.

### 3. Blocking Issues
Each `❌ FAIL` with: Rule ID, file + line, exact remediation.

### 4. Commit Verdict
**`✅ APPROVED`** — all rules pass.
**`❌ BLOCKED`** — one or more failures; do not commit until resolved.
