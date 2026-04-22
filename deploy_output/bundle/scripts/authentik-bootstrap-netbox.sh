#!/bin/sh
set -eu

# Set the akadmin password from the dedicated secret so it is deterministic
# across greenfield deployments rather than Authentik's random bootstrap token.
if [ -f /run/secrets/authentik_admin_password ]; then
  export AKADMIN_PW
  AKADMIN_PW="$(cat /run/secrets/authentik_admin_password | tr -d '\n')"
  /ak-root/.venv/bin/python -u -m manage shell <<PYEOF
import os
from authentik.core.models import User
pw = os.environ.get('AKADMIN_PW', '').strip()
if pw:
    u = User.objects.filter(username='akadmin').first()
    if u:
        u.set_password(pw)
        u.save()
        print('authentik-bootstrap-netbox: akadmin password set from secret')
    else:
        print('authentik-bootstrap-netbox: akadmin user not found, skipping')
PYEOF
fi

/ak-root/.venv/bin/python -u -m manage shell <<'PY'
import os

from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.core.models import PropertyMapping
from authentik.outposts.models import Outpost
from authentik.providers.oauth2.models import RedirectURI, RedirectURIMatchingMode
from authentik.providers.proxy.models import ProxyMode, ProxyProvider

public_url = os.environ["NETBOX_PUBLIC_URL"].rstrip("/")
internal_url = os.environ.get("NETBOX_INTERNAL_URL", "http://waf:8081").rstrip("/")
callback_url = (
  f"{public_url}/outpost.goauthentik.io/callback"
  "?X-authentik-auth-callback=true"
)

auth_flow = Flow.objects.get(slug="default-authentication-flow")
authorization_flow = Flow.objects.get(
  slug="default-provider-authorization-implicit-consent"
)

provider, created = ProxyProvider.objects.update_or_create(
  name="NetBox Proxy Provider",
  defaults={
    "authentication_flow": auth_flow,
    "authorization_flow": authorization_flow,
    "external_host": public_url,
    "internal_host": internal_url,
    "mode": ProxyMode.FORWARD_SINGLE,
  },
)
provider.redirect_uris = [
  RedirectURI(
    matching_mode=RedirectURIMatchingMode.STRICT,
    url=callback_url,
  )
]
provider.property_mappings.set([
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: OpenID 'openid'"),
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: OpenID 'profile'"),
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: OpenID 'email'"),
  PropertyMapping.objects.get(name="authentik default OAuth Mapping: Proxy outpost"),
])
provider.save()

application, _ = Application.objects.update_or_create(
  slug="netbox",
  defaults={
    "name": "NetBox",
    "provider": provider,
    "meta_launch_url": public_url,
  },
)

embedded_outpost = Outpost.objects.get(name="authentik Embedded Outpost")
embedded_outpost_config = embedded_outpost.config
embedded_outpost_config.authentik_host = public_url
embedded_outpost_config.authentik_host_browser = public_url
embedded_outpost.config = embedded_outpost_config
embedded_outpost.save()
embedded_outpost.providers.add(provider)

print(
  "authentik-bootstrap-netbox:",
  f"provider={'created' if created else 'updated'}",
  f"application={application.slug}",
  f"public_url={public_url}",
  f"internal_url={internal_url}",
  f"callback_url={callback_url}",
)
PY
