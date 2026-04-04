#!/usr/bin/env python3
"""Import device-type-library YAML files into NetBox via its REST API.

Creates manufacturers, device types (with component templates),
module types (with component templates), and rack types.
Idempotent: existing objects are skipped.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen, urlretrieve

import yaml

# ── YAML keys that are NOT device-/module-type API fields ──
COMPONENT_KEYS = frozenset({
    "interfaces", "console-ports", "console-server-ports",
    "power-ports", "power-outlets", "front-ports", "rear-ports",
    "device-bays", "module-bays", "inventory-items",
})
DTLI_ONLY_KEYS = frozenset({
    "manufacturer", "is_powered", "front_image", "rear_image",
})

# YAML key → API list endpoint (relative to /api/dcim/)
COMPONENT_ENDPOINTS: dict[str, str] = {
    "interfaces":           "interface-templates",
    "console-ports":        "console-port-templates",
    "console-server-ports": "console-server-port-templates",
    "power-ports":          "power-port-templates",
    "power-outlets":        "power-outlet-templates",
    "rear-ports":           "rear-port-templates",
    "front-ports":          "front-port-templates",
    "device-bays":          "device-bay-templates",
    "module-bays":          "module-bay-templates",
    "inventory-items":      "inventory-item-templates",
}

# Component keys whose items may reference another template by name.
# Maps yaml_key → (field_in_yaml, api_field_name, referenced_yaml_key)
COMPONENT_REFS: dict[str, tuple[str, str, str]] = {
    "power-outlets": ("power_port", "power_port_template", "power-ports"),
    "front-ports":   ("rear_port",  "rear_port_template",  "rear-ports"),
}

# ── helpers ──

def _slugify(value: str) -> str:
    return re.sub(r"\W+", "-", value.casefold()).strip("-")


def _split_csv(value: str) -> set[str]:
    return {item.strip().casefold() for item in value.split(",") if item.strip()}


# ── lightweight REST client (stdlib only) ──

class NetBoxAPI:
    def __init__(self, base_url: str, bearer_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # -- low level --

    def _request(self, method: str, path: str, body: object = None,
                 params: dict[str, str] | None = None) -> tuple[int, object]:
        url = f"{self._base}{path}"
        if params:
            url += "?" + urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = Request(url, data=data, method=method, headers=self._headers)
        try:
            with urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def get(self, path: str, **params: str) -> tuple[int, object]:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: object) -> tuple[int, object]:
        return self._request("POST", path, body)

    # -- convenience --

    def get_or_create(self, path: str, lookup: dict[str, str],
                      create: dict[str, object]) -> tuple[dict, bool]:
        status, data = self.get(path, **lookup)
        if status == 200 and data.get("count", 0) > 0:
            return data["results"][0], False
        status, data = self.post(path, create)
        if status == 201:
            return data, True
        # Race or slug collision: retry by original lookup then by slug
        if status == 400:
            status2, data2 = self.get(path, **lookup)
            if status2 == 200 and data2.get("count", 0) > 0:
                return data2["results"][0], False
            slug = create.get("slug")
            if slug:
                status3, data3 = self.get(path, slug=slug)
                if status3 == 200 and data3.get("count", 0) > 0:
                    return data3["results"][0], False
        raise RuntimeError(f"Failed to create {path}: HTTP {status}: {data}")

    def bulk_create(self, path: str, items: list[dict]) -> list[dict]:
        if not items:
            return []
        status, data = self.post(path, items)
        if status == 201:
            return data if isinstance(data, list) else [data]
        raise RuntimeError(f"Bulk create {path}: HTTP {status}: {data}")


# ── library download ──

def _download_library() -> Path:
    archive_url = os.environ["DEVICE_TYPE_LIBRARY_ARCHIVE_URL"]
    working_dir = Path(tempfile.mkdtemp(prefix="netbox-device-library-"))
    archive_path = working_dir / "library.tar.gz"
    extract_dir = working_dir / "extract"
    extract_dir.mkdir(parents=True, exist_ok=True)

    urlretrieve(archive_url, archive_path)
    with tarfile.open(archive_path, mode="r:gz") as archive:
        archive.extractall(extract_dir)

    roots = sorted(p for p in extract_dir.iterdir() if p.is_dir())
    if not roots:
        raise RuntimeError(f"Archive empty: {archive_url}")
    return roots[0]


def _iter_definition_files(root: Path, directory_name: str,
                           vendors: set[str]) -> list[Path]:
    base_dir = root / directory_name
    if not base_dir.exists():
        return []
    files: list[Path] = []
    for vendor_dir in sorted(p for p in base_dir.iterdir() if p.is_dir()):
        if vendors and vendor_dir.name.casefold() not in vendors:
            continue
        for pattern in ("*.yaml", "*.yml"):
            files.extend(sorted(vendor_dir.glob(pattern)))
    return files


def _load_documents(paths: list[Path]) -> list[tuple[Path, dict[str, object]]]:
    docs: list[tuple[Path, dict[str, object]]] = []
    for path in paths:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            raise RuntimeError(f"Expected YAML object in {path}")
        docs.append((path, doc))
    return docs


# ── import logic ──

def _collect_manufacturers(
    *doc_sets: list[tuple[Path, dict[str, object]]],
) -> dict[str, dict[str, str]]:
    mfgs: dict[str, dict[str, str]] = {}
    for doc_set in doc_sets:
        for _, doc in doc_set:
            name = doc.get("manufacturer")
            if isinstance(name, str) and name not in mfgs:
                mfgs[name] = {"name": name, "slug": _slugify(name)}
    return mfgs


def _import_manufacturers(api: NetBoxAPI,
                          mfgs: dict[str, dict[str, str]]) -> dict[str, int]:
    name_to_id: dict[str, int] = {}
    for name in sorted(mfgs, key=str.casefold):
        obj, created = api.get_or_create(
            "/api/dcim/manufacturers/",
            lookup={"name": name},
            create=mfgs[name],
        )
        name_to_id[name] = obj["id"]
        tag = "created" if created else "exists"
        print(f"  {tag}: {name} (id={obj['id']})")
    return name_to_id


def _import_components(api: NetBoxAPI, parent_key: str, parent_id: int,
                       doc: dict[str, object],
                       mfg_ids: dict[str, int] | None = None) -> None:
    """Import component templates for a device type or module type."""
    # First pass: components that do NOT reference other templates.
    created_name_ids: dict[str, dict[str, int]] = {}
    for yaml_key in (
        "interfaces", "console-ports", "console-server-ports",
        "power-ports", "rear-ports",
        "device-bays", "module-bays", "inventory-items",
    ):
        items = doc.get(yaml_key)
        if not items:
            continue
        endpoint = f"/api/dcim/{COMPONENT_ENDPOINTS[yaml_key]}/"
        api_items = []
        for item in items:
            api_item: dict[str, object] = {parent_key: parent_id, **item}
            # Resolve manufacturer name -> ID for inventory items
            if "manufacturer" in api_item and mfg_ids:
                mfg_val = api_item["manufacturer"]
                if isinstance(mfg_val, str):
                    resolved = mfg_ids.get(mfg_val)
                    if resolved is not None:
                        api_item["manufacturer"] = resolved
                    else:
                        del api_item["manufacturer"]
            api_items.append(api_item)
        try:
            results = api.bulk_create(endpoint, api_items)
        except RuntimeError as exc:
            print(f"    {yaml_key}: ERROR {exc}")
            continue
        created_name_ids[yaml_key] = {r["name"]: r["id"] for r in results}
        print(f"    {yaml_key}: {len(results)}")

    # Second pass: components that reference templates created above.
    for yaml_key, (src_field, api_field, ref_key) in COMPONENT_REFS.items():
        items = doc.get(yaml_key)
        if not items:
            continue
        ref_ids = created_name_ids.get(ref_key, {})
        endpoint = f"/api/dcim/{COMPONENT_ENDPOINTS[yaml_key]}/"
        api_items = []
        for item in items:
            api_item: dict[str, object] = {parent_key: parent_id}
            for k, v in item.items():
                if k == src_field and isinstance(v, str):
                    tid = ref_ids.get(v)
                    if tid is not None:
                        api_item[api_field] = tid
                else:
                    api_item[k] = v
            api_items.append(api_item)
        try:
            results = api.bulk_create(endpoint, api_items)
        except RuntimeError as exc:
            print(f"    {yaml_key}: ERROR {exc}")
            continue
        print(f"    {yaml_key}: {len(results)}")


def _import_device_types(api: NetBoxAPI, documents: list[tuple[Path, dict]],
                         mfg_ids: dict[str, int]) -> None:
    for path, doc in documents:
        mfg_name = doc["manufacturer"]
        model = doc.get("model", path.stem)
        slug = doc.get("slug", _slugify(f"{mfg_name}-{model}"))
        payload: dict[str, object] = {
            "manufacturer": mfg_ids[mfg_name], "model": model, "slug": slug,
        }
        for k, v in doc.items():
            if k not in COMPONENT_KEYS and k not in DTLI_ONLY_KEYS and k not in ("model", "slug"):
                payload[k] = v

        try:
            obj, created = api.get_or_create(
                "/api/dcim/device-types/",
                lookup={"slug": slug},
                create=payload,
            )
        except RuntimeError as exc:
            print(f"  ERROR {path.name}: {exc}")
            continue
        tag = "created" if created else "exists"
        print(f"  {tag}: {model} [{slug}] (id={obj['id']})")
        if created:
            _import_components(api, "device_type", obj["id"], doc, mfg_ids)


def _import_module_types(api: NetBoxAPI, documents: list[tuple[Path, dict]],
                         mfg_ids: dict[str, int]) -> None:
    for path, doc in documents:
        mfg_name = doc["manufacturer"]
        model = doc.get("model", path.stem)
        payload: dict[str, object] = {
            "manufacturer": mfg_ids[mfg_name], "model": model,
        }
        for k, v in doc.items():
            if k not in COMPONENT_KEYS and k not in DTLI_ONLY_KEYS and k != "model":
                payload[k] = v

        try:
            obj, created = api.get_or_create(
                "/api/dcim/module-types/",
                lookup={"manufacturer_id": str(mfg_ids[mfg_name]), "model": model},
                create=payload,
            )
        except RuntimeError as exc:
            print(f"  ERROR {path.name}: {exc}")
            continue
        tag = "created" if created else "exists"
        print(f"  {tag}: {model} (id={obj['id']})")
        if created:
            _import_components(api, "module_type", obj["id"], doc, mfg_ids)


def _import_rack_types(api: NetBoxAPI, documents: list[tuple[Path, dict]],
                       mfg_ids: dict[str, int]) -> None:
    for path, doc in documents:
        mfg_name = doc["manufacturer"]
        model = doc.get("model", path.stem)
        slug = doc.get("slug", _slugify(f"{mfg_name}-{model}"))
        payload: dict[str, object] = {
            "manufacturer": mfg_ids[mfg_name], "model": model, "slug": slug,
        }
        for k, v in doc.items():
            if k not in DTLI_ONLY_KEYS and k not in ("model", "slug"):
                payload[k] = v

        try:
            obj, created = api.get_or_create(
                "/api/dcim/rack-types/",
                lookup={"slug": slug},
                create=payload,
            )
        except RuntimeError as exc:
            print(f"  ERROR {path.name}: {exc}")
            continue
        tag = "created" if created else "exists"
        print(f"  {tag}: {model} [{slug}] (id={obj['id']})")


# ── token construction ──

def _build_bearer_token() -> str:
    """Read the API token plaintext from secrets and look up the DB key."""
    sys.path.insert(0, "/opt/netbox/netbox")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

    import django
    django.setup()

    from django.contrib.auth import get_user_model
    from users.models import Token

    plaintext = Path("/run/secrets/superuser_api_token").read_text("utf-8").strip()
    if not plaintext:
        raise RuntimeError("superuser_api_token secret is empty")

    username_file = os.environ.get("NETBOX_IMPORT_USERNAME_FILE", "/run/secrets/superuser_name")
    username = Path(username_file).read_text("utf-8").strip()

    User = get_user_model()
    user = User.objects.get(username=username)

    for token in Token.objects.filter(user=user):
        if token.validate(plaintext):
            return f"nbt_{token.key}.{plaintext}"

    raise RuntimeError("No matching API token found for the configured user")


# ── main ──

def main() -> None:
    bearer = _build_bearer_token()
    netbox_url = os.environ["NETBOX_URL"].rstrip("/")
    api = NetBoxAPI(netbox_url, bearer)

    status, data = api.get("/api/status/")
    if status != 200:
        raise RuntimeError(f"NetBox API unreachable: HTTP {status}")
    print(f"Connected to NetBox {data.get('netbox-version', '?')}")

    vendors = _split_csv(os.environ.get("DEVICE_TYPE_LIBRARY_VENDORS", ""))
    library_root = _download_library()

    device_docs = _load_documents(_iter_definition_files(library_root, "device-types", vendors))
    module_docs = _load_documents(_iter_definition_files(library_root, "module-types", vendors))
    rack_docs = _load_documents(_iter_definition_files(library_root, "rack-types", vendors))
    print(
        f"Loaded {len(device_docs)} device, {len(module_docs)} module,"
        f" {len(rack_docs)} rack definitions"
    )

    mfgs = _collect_manufacturers(device_docs, module_docs, rack_docs)
    print(f"Importing {len(mfgs)} manufacturers ...")
    mfg_ids = _import_manufacturers(api, mfgs)

    if device_docs:
        print(f"Importing {len(device_docs)} device types ...")
        _import_device_types(api, device_docs, mfg_ids)

    if module_docs:
        print(f"Importing {len(module_docs)} module types ...")
        _import_module_types(api, module_docs, mfg_ids)

    if rack_docs:
        print(f"Importing {len(rack_docs)} rack types ...")
        _import_rack_types(api, rack_docs, mfg_ids)

    print("Import complete.")


if __name__ == "__main__":
    main()
