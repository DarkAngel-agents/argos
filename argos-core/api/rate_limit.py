"""
Shared slowapi Limiter — single instance imported by every router that
declares per-endpoint rate limits, plus by main.py for the exception
handler / state wiring.

Lives in its own module so router files can import it without pulling in
api.main (which imports them in turn — circular).

Audit H4. Keyed on remote IP address (works behind a single-node deploy;
behind a reverse proxy you'll want to configure ProxyHeadersMiddleware
or an X-Forwarded-For aware key_func).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Audit N4: default_limits applied globally via SlowAPIMiddleware so they run
# BEFORE the auth dependency. This catches requests that fail auth and would
# otherwise consume zero rate-limit budget. Per-route @limiter.limit values
# layer on top (most restrictive wins per request).
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["600/minute"],
    storage_uri="redis://argos-redis:6379",
    in_memory_fallback_enabled=True,
    headers_enabled=True,
)
