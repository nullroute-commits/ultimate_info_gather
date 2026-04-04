#!/bin/sh
set -eu

if [ ! -f /run/secrets/superuser_name ] || [ ! -f /run/secrets/superuser_password ]; then
  echo "Missing required superuser secret files" >&2
  exit 1
fi

NB_SUPERUSER_NAME="$(cat /run/secrets/superuser_name)"
NB_SUPERUSER_PASSWORD="$(cat /run/secrets/superuser_password)"
NB_SUPERUSER_API_TOKEN=""
if [ -f /run/secrets/superuser_api_token ]; then
  NB_SUPERUSER_API_TOKEN="$(cat /run/secrets/superuser_api_token)"
fi

export NB_SUPERUSER_NAME NB_SUPERUSER_PASSWORD NB_SUPERUSER_API_TOKEN
/opt/netbox/venv/bin/python -u /opt/netbox/netbox/manage.py shell <<'PY'
from django.contrib.auth import get_user_model
import os

username = os.environ["NB_SUPERUSER_NAME"].strip()
password = os.environ["NB_SUPERUSER_PASSWORD"]
api_token_key = os.environ.get("NB_SUPERUSER_API_TOKEN", "").strip()

if not username:
  raise RuntimeError("Superuser name secret is empty")

user_model = get_user_model()
user, created = user_model.objects.get_or_create(
  username=username,
  defaults={"is_superuser": True, "is_active": True},
)

changed = created
if not user.is_superuser:
  user.is_superuser = True
  changed = True
if not user.is_active:
  user.is_active = True
  changed = True
if not user.check_password(password):
  user.set_password(password)
  changed = True

if changed:
  user.save()

# Ensure a v2 API token exists for this user
if api_token_key:
  from django.conf import settings
  from users.models import Token
  from users.choices import TokenVersionChoices
  if settings.API_TOKEN_PEPPERS:
    existing = None
    for t in Token.objects.filter(user=user):
      if t.validate(api_token_key):
        existing = t
        break
    if not existing:
      Token.objects.filter(user=user).delete()
      t = Token.objects.create(user=user, token=api_token_key, version=TokenVersionChoices.V2)
      changed = True
      print(f"superuser-sync: created v2 token key={t.key}")
    else:
      t = existing
      print(f"superuser-sync: token already exists key={existing.key}")

    # Write the full v2 token (nbt_<key>.<plaintext>) for sidecar services
    full_token = f"nbt_{t.key}.{api_token_key}"
    from pathlib import Path
    token_store = Path("/token-store")
    if token_store.is_dir():
      (token_store / "api_token").write_text(full_token)
      print("superuser-sync: wrote full v2 token to /token-store/api_token")

print(f"superuser-sync: username={user.username} changed={changed}")
PY
