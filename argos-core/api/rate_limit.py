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

limiter = Limiter(key_func=get_remote_address)
