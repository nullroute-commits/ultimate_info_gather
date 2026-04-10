#!/bin/sh
set -eu

DIODE_CLIENT_SECRET=""
if [ -f /run/secrets/netbox_to_diode ]; then
  DIODE_CLIENT_SECRET="$(cat /run/secrets/netbox_to_diode)"
fi

export DIODE_CLIENT_SECRET
/opt/netbox/venv/bin/python -u /opt/netbox/netbox/manage.py shell <<'PY'
from django.contrib.auth import get_user_model
import os

username = "diode"
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
if changed:
  user.save()

print(f"diode-setup: user='{username}' created={created} changed={changed}")

# Ensure an API token exists for the diode user
from users.models import Token
tokens = Token.objects.filter(user=user)
if not tokens.exists():
  token = Token.objects.create(user=user)
  print(f"diode-setup: created API token key={token.key}")
else:
  print(f"diode-setup: API token already exists for '{username}'")
PY
